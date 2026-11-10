from wabot.store import MessageStore


def make(tmp_path):
    return MessageStore(str(tmp_path / "h.db"))


def test_recent_returns_chronological_role_text_pairs(tmp_path):
    store = make(tmp_path)
    store.add_turn("111", "user", "hola")
    store.add_turn("111", "assistant", "buenas")
    store.add_turn("111", "user", "precio?")
    assert store.recent("111", 10) == [("user", "hola"), ("assistant", "buenas"), ("user", "precio?")]


def test_recent_limits_to_last_n(tmp_path):
    store = make(tmp_path)
    for i in range(5):
        store.add_turn("111", "user", f"m{i}")
    assert store.recent("111", 2) == [("user", "m3"), ("user", "m4")]


def test_recent_is_isolated_per_sender(tmp_path):
    store = make(tmp_path)
    store.add_turn("111", "user", "a")
    store.add_turn("222", "user", "b")
    assert store.recent("111", 10) == [("user", "a")]
    assert store.recent("333", 10) == []


def test_history_survives_reopen(tmp_path):
    make(tmp_path).add_turn("111", "user", "hola")
    assert make(tmp_path).recent("111", 10) == [("user", "hola")]
