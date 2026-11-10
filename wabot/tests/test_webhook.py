import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from wabot import app as app_module
from wabot.config import Settings
from wabot.store import MessageStore

APP_SECRET = "test-secret"
VERIFY_TOKEN = "test-verify"


def sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def inbound_payload(message_id: str = "wamid.A1", text: str = "hola", sender: str = "5491100000000") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "PNID"},
                            "contacts": [{"wa_id": sender}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def status_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "PNID"},
                            "statuses": [{"id": "wamid.X", "status": "delivered"}],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sent():
    return []


@pytest.fixture
def client(tmp_path, sent):
    settings = Settings(
        verify_token=VERIFY_TOKEN,
        app_secret=APP_SECRET,
        access_token="tok",
        phone_number_id="PNID",
        graph_api_version="v0.0",
        db_path=str(tmp_path / "wabot.db"),
        owner_phone_number="5491100000000",
    )

    async def fake_send(to: str, text: str) -> None:
        sent.append((to, text))

    def responder(text: str, history: list) -> str:
        return f"re:{text}|h={len(history)}"

    application = app_module.create_app(
        settings=settings, sender=fake_send, store=MessageStore(settings.db_path), responder=responder
    )
    return TestClient(application)


def post(client: TestClient, payload: dict, signature: str | None = "auto"):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "auto":
        headers["X-Hub-Signature-256"] = sign(body)
    elif signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return client.post("/webhook", content=body, headers=headers)


def test_verification_handshake_returns_challenge(client):
    r = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"},
    )
    assert r.status_code == 200
    assert r.text == "12345"


def test_verification_rejects_wrong_token(client):
    r = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "12345"},
    )
    assert r.status_code == 403


def test_post_without_signature_is_rejected(client, sent):
    r = post(client, inbound_payload(), signature=None)
    assert r.status_code == 403
    assert sent == []


def test_post_with_bad_signature_is_rejected(client, sent):
    r = post(client, inbound_payload(), signature="sha256=" + "0" * 64)
    assert r.status_code == 403
    assert sent == []


def test_post_with_signature_from_other_secret_is_rejected(client, sent):
    body = json.dumps(inbound_payload()).encode()
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sign(body, "other"), "Content-Type": "application/json"},
    )
    assert r.status_code == 403
    assert sent == []


def test_valid_text_message_gets_responder_reply(client, sent):
    r = post(client, inbound_payload(text="hola mayorista"))
    assert r.status_code == 200
    assert sent == [("5491100000000", "re:hola mayorista|h=0")]


def test_second_message_sees_previous_turns_as_history(client, sent):
    post(client, inbound_payload(message_id="wamid.1", text="uno"))
    post(client, inbound_payload(message_id="wamid.2", text="dos"))
    assert sent[1][1] == "re:dos|h=2"


def test_responder_failure_releases_message_and_stores_nothing(tmp_path):
    attempts = []

    def flaky(text: str, history: list) -> str:
        attempts.append(history)
        if len(attempts) == 1:
            raise RuntimeError("ollama down")
        return "ok"

    async def send(to: str, text: str) -> None:
        pass

    store = MessageStore(str(tmp_path / "w.db"))
    settings = Settings(VERIFY_TOKEN, APP_SECRET, "tok", "PNID", "v0.0", str(tmp_path / "w.db"), "5491100000000")
    c = TestClient(app_module.create_app(settings=settings, sender=send, store=store, responder=flaky))
    post(c, inbound_payload(message_id="wamid.F"))
    assert store.recent("5491100000000", 10) == []
    post(c, inbound_payload(message_id="wamid.F"))
    assert len(attempts) == 2 and attempts[1] == []
    assert store.recent("5491100000000", 10) == [("user", "hola"), ("assistant", "ok")]


def test_duplicate_message_id_is_answered_once(client, sent):
    post(client, inbound_payload(message_id="wamid.DUP"))
    r = post(client, inbound_payload(message_id="wamid.DUP"))
    assert r.status_code == 200
    assert len(sent) == 1


def test_distinct_message_ids_are_both_answered(client, sent):
    post(client, inbound_payload(message_id="wamid.1", text="uno"))
    post(client, inbound_payload(message_id="wamid.2", text="dos"))
    assert [t for _, t in sent] == ["re:uno|h=0", "re:dos|h=2"]


def test_status_updates_are_acknowledged_without_reply(client, sent):
    r = post(client, status_payload())
    assert r.status_code == 200
    assert sent == []


def test_image_message_gets_text_only_notice_and_200(client, sent):
    payload = inbound_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"][0] = {
        "from": "5491100000000",
        "id": "wamid.IMG",
        "type": "image",
        "image": {"id": "media1"},
    }
    r = post(client, payload)
    assert r.status_code == 200
    assert len(sent) == 1 and "texto" in sent[0][1]


def test_malformed_json_with_valid_signature_returns_200_without_reply(client, sent):
    body = b"{not json"
    r = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert sent == []


def test_send_failure_does_not_break_webhook_and_message_can_be_retried(tmp_path):
    attempts = []

    async def flaky_send(to: str, text: str) -> None:
        attempts.append((to, text))
        if len(attempts) == 1:
            raise RuntimeError("graph down")

    settings = Settings(
        verify_token=VERIFY_TOKEN,
        app_secret=APP_SECRET,
        access_token="tok",
        phone_number_id="PNID",
        graph_api_version="v0.0",
        db_path=str(tmp_path / "wabot.db"),
        owner_phone_number="5491100000000",
    )
    application = app_module.create_app(
        settings=settings, sender=flaky_send, store=MessageStore(settings.db_path), responder=lambda t, h: t
    )
    c = TestClient(application)
    assert post(c, inbound_payload(message_id="wamid.R")).status_code == 200
    assert post(c, inbound_payload(message_id="wamid.R")).status_code == 200
    assert len(attempts) == 2


def test_normalize_recipient_drops_argentine_mobile_nine():
    from wabot.whatsapp import normalize_recipient

    assert normalize_recipient("5491112345678") == "541112345678"
    assert normalize_recipient("541112345678") == "541112345678"
    assert normalize_recipient("16315551181") == "16315551181"


def media_payload(kind: str, message_id: str = "wamid.M1", sender: str = "5491100000000") -> dict:
    payload = inbound_payload(message_id=message_id, sender=sender)
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message["type"] = kind
    message.pop("text")
    message[kind] = {"id": "MEDIA1", "mime_type": "x/y"}
    return payload


@pytest.mark.parametrize("kind", ["audio", "image", "video", "document"])
def test_unsupported_media_gets_text_only_notice_with_owner_link(client, sent, kind):
    r = post(client, media_payload(kind))
    assert r.status_code == 200
    assert len(sent) == 1
    to, text = sent[0]
    assert to == "5491100000000"
    assert "solo" in text and "texto" in text
    assert "https://wa.me/5491100000000" in text


@pytest.mark.parametrize("kind", ["reaction", "sticker", "unsupported", "system"])
def test_other_message_types_are_ignored_silently(client, sent, kind):
    r = post(client, media_payload(kind))
    assert r.status_code == 200
    assert sent == []


def test_unsupported_media_is_deduplicated_and_not_stored_in_history(tmp_path):
    sent = []

    async def send(to: str, text: str) -> None:
        sent.append(text)

    store = MessageStore(str(tmp_path / "w.db"))
    settings = Settings(VERIFY_TOKEN, APP_SECRET, "tok", "PNID", "v0.0", str(tmp_path / "w.db"), "5491100000000")
    c = TestClient(app_module.create_app(settings=settings, sender=send, store=store, responder=lambda t, h: "x"))
    post(c, media_payload("audio", message_id="wamid.D"))
    post(c, media_payload("audio", message_id="wamid.D"))
    assert len(sent) == 1
    assert store.recent("5491100000000", 10) == []


def _burst_app(tmp_path, delay):
    import time

    sent = []

    async def send(to: str, text: str) -> None:
        sent.append((to, text))

    def responder(text: str, history: list) -> str:
        time.sleep(delay)
        return f"h={len(history)}"

    store = MessageStore(str(tmp_path / "w.db"))
    settings = Settings(VERIFY_TOKEN, APP_SECRET, "tok", "PNID", "v0.0", str(tmp_path / "w.db"), "5491100000000")
    return app_module.create_app(settings=settings, sender=send, store=store, responder=responder), sent, store


def _fire(application, payloads):
    import asyncio

    import httpx

    async def go():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            async def one(p):
                body = json.dumps(p).encode()
                return await c.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body), "Content-Type": "application/json"})

            return await asyncio.gather(*[one(p) for p in payloads])

    return asyncio.run(go())


def test_same_sender_burst_is_processed_in_order_with_shared_history(tmp_path):
    application, sent, store = _burst_app(tmp_path, 0.2)
    _fire(application, [inbound_payload(message_id="wamid.B1", text="uno"), inbound_payload(message_id="wamid.B2", text="dos")])
    assert sorted(t for _, t in sent) == ["h=0", "h=2"]
    roles = [r for r, _ in store.recent("5491100000000", 10)]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_different_senders_are_processed_in_parallel(tmp_path):
    import time

    application, sent, _ = _burst_app(tmp_path, 0.4)
    started = time.time()
    _fire(
        application,
        [inbound_payload(message_id="wamid.P1", sender="5491100000001"), inbound_payload(message_id="wamid.P2", sender="5491100000002")],
    )
    assert len(sent) == 2
    assert time.time() - started < 0.75
