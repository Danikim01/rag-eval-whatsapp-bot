from fastapi.testclient import TestClient

from wabot import app as app_module
from wabot.config import Settings
from wabot.store import MessageStore


def make_client(tmp_path, store=None):
    settings = Settings("v", "s", "tok", "PNID", "v0.0", str(tmp_path / "t.db"), "5491100000000")
    store = store or MessageStore(settings.db_path)

    async def sender(to, text):
        return None

    return TestClient(app_module.create_app(settings=settings, sender=sender, store=store, responder=lambda t, h: "ok"))


def test_health_returns_ok_without_secrets(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "tok" not in response.text


def test_health_returns_503_when_database_fails(tmp_path):
    store = MessageStore(str(tmp_path / "t.db"))

    def broken():
        raise RuntimeError("db down")

    store.ping = broken
    with make_client(tmp_path, store) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert "db down" not in response.text
