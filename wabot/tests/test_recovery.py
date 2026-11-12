from fastapi.testclient import TestClient

from wabot import app as app_module
from wabot.config import Settings
from wabot.store import MessageStore


def make_settings(tmp_path):
    return Settings("v", "s", "tok", "PNID", "v0.0", str(tmp_path / "r.db"), "5491100000000")


def test_startup_replays_pending_message_and_replies(tmp_path):
    settings = make_settings(tmp_path)
    store = MessageStore(settings.db_path)
    store.enqueue("w1", "5491111111111", "hola")
    sent = []

    async def sender(to, text):
        sent.append((to, text))

    app = app_module.create_app(settings, sender=sender, store=store, responder=lambda q, h: "buenas")
    with TestClient(app):
        pass
    assert sent == [("5491111111111", "buenas")]
    assert store.is_done("w1")
    assert store.pending() == []


def test_startup_does_not_replay_done_messages(tmp_path):
    settings = make_settings(tmp_path)
    store = MessageStore(settings.db_path)
    store.enqueue("w1", "5491111111111", "hola")
    store.complete("w1", "5491111111111", "hola", "buenas")
    sent = []

    async def sender(to, text):
        sent.append((to, text))

    app = app_module.create_app(settings, sender=sender, store=store, responder=lambda q, h: "x")
    with TestClient(app):
        pass
    assert sent == []


def test_failed_reply_stays_pending_and_gives_up_after_max_attempts(tmp_path):
    settings = make_settings(tmp_path)
    store = MessageStore(settings.db_path)
    store.enqueue("w1", "5491111111111", "hola")

    def boom(q, h):
        raise RuntimeError("llm down")

    async def sender(to, text):
        pass

    app = app_module.create_app(settings, sender=sender, store=store, responder=boom)
    for _ in range(app_module.MAX_ATTEMPTS):
        assert len(store.pending()) == 1
        with TestClient(app):
            pass
    assert store.pending() == []


def test_startup_prunes_old_data(tmp_path):
    import sqlite3

    settings = make_settings(tmp_path)
    store = MessageStore(settings.db_path)
    store.add_turn("111", "user", "viejo")
    with sqlite3.connect(settings.db_path) as raw:
        raw.execute("UPDATE turns SET created_at = datetime('now', '-4000 days')")

    async def sender(to, text):
        pass

    app = app_module.create_app(settings, sender=sender, store=store, responder=lambda q, h: "x")
    with TestClient(app):
        pass
    assert store.recent("111", 10) == []


def test_webhook_persists_message_before_ack(tmp_path):
    import hashlib
    import hmac
    import json

    settings = make_settings(tmp_path)
    store = MessageStore(settings.db_path)

    async def sender(to, text):
        raise RuntimeError("send down")

    app = app_module.create_app(settings, sender=sender, store=store, responder=lambda q, h: "x")
    body = json.dumps(
        {"entry": [{"changes": [{"field": "messages", "value": {"messages": [
            {"from": "5491111111111", "id": "w9", "type": "text", "text": {"body": "hola"}}
        ]}}]}]}
    ).encode()
    sig = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
    client = TestClient(app)
    r = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200
    assert store.pending() == [("w9", "5491111111111", "hola")]
