import sqlite3

from wabot.store import MessageStore


def make(tmp_path):
    return MessageStore(str(tmp_path / "i.db"))


def test_enqueue_persists_message_as_pending(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    assert store.pending() == [("w1", "111", "hola")]


def test_enqueue_is_idempotent(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    store.enqueue("w1", "111", "hola")
    assert len(store.pending()) == 1


def test_pending_survives_reopen(tmp_path):
    make(tmp_path).enqueue("w1", "111", "hola")
    assert make(tmp_path).pending() == [("w1", "111", "hola")]


def test_complete_marks_done_and_stores_both_turns(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    store.complete("w1", "111", "hola", "buenas")
    assert store.pending() == []
    assert store.is_done("w1")
    assert store.recent("111", 10) == [("user", "hola"), ("assistant", "buenas")]


def test_is_done_false_for_unknown_and_pending(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    assert not store.is_done("w1")
    assert not store.is_done("nope")


def test_pending_is_ordered_by_arrival(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "a")
    store.enqueue("w2", "222", "b")
    assert [m for m, _, _ in store.pending()] == ["w1", "w2"]


def test_record_failure_marks_dead_after_max_attempts(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    store.record_failure("w1", max_attempts=2)
    assert len(store.pending()) == 1
    store.record_failure("w1", max_attempts=2)
    assert store.pending() == []


def test_pending_marks_stale_messages_dead(tmp_path):
    store = make(tmp_path)
    store.enqueue("w1", "111", "hola")
    with sqlite3.connect(str(tmp_path / "i.db")) as raw:
        raw.execute("UPDATE inbox SET created_at = datetime('now', '-25 hours')")
    assert store.pending(max_age_hours=24) == []


def test_prune_deletes_old_rows_and_keeps_recent(tmp_path):
    store = make(tmp_path)
    store.enqueue("old", "111", "x")
    store.complete("old", "111", "x", "y")
    store.enqueue("new", "111", "z")
    store.complete("new", "111", "z", "w")
    with sqlite3.connect(str(tmp_path / "i.db")) as raw:
        raw.execute("UPDATE turns SET created_at = datetime('now', '-400 days') WHERE text IN ('x','y')")
        raw.execute("UPDATE inbox SET created_at = datetime('now', '-400 days') WHERE message_id = 'old'")
    store.prune(retention_days=365, max_turns_per_sender=100)
    assert store.recent("111", 10) == [("user", "z"), ("assistant", "w")]
    assert not store.is_done("old")
    assert store.is_done("new")


def test_prune_caps_turns_per_sender_keeping_newest(tmp_path):
    store = make(tmp_path)
    for i in range(10):
        store.add_turn("111", "user", f"m{i}")
    store.add_turn("222", "user", "other")
    store.prune(retention_days=365, max_turns_per_sender=3)
    assert store.recent("111", 10) == [("user", "m7"), ("user", "m8"), ("user", "m9")]
    assert store.recent("222", 10) == [("user", "other")]


def test_prune_deletes_old_processed_message_claims(tmp_path):
    store = make(tmp_path)
    store.claim("u1")
    with sqlite3.connect(str(tmp_path / "i.db")) as raw:
        raw.execute("UPDATE processed_messages SET created_at = datetime('now', '-400 days')")
    store.prune(retention_days=365, max_turns_per_sender=100)
    assert store.claim("u1")
