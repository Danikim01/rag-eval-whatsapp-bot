import hashlib
import hmac
import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger("wabot")


@dataclass(frozen=True)
class InboundText:
    message_id: str
    sender: str
    text: str


@dataclass(frozen=True)
class InboundUnsupported:
    message_id: str
    sender: str
    kind: str


UNSUPPORTED_REPLY_KINDS = frozenset({"audio", "image", "video", "document"})


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def extract_text_messages(payload: dict) -> list[InboundText]:
    found: list[InboundText] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue
                body = (message.get("text") or {}).get("body")
                message_id = message.get("id")
                sender = message.get("from")
                if body and message_id and sender:
                    found.append(InboundText(message_id=message_id, sender=sender, text=body))
    return found


def extract_unsupported_messages(payload: dict) -> list[InboundUnsupported]:
    found: list[InboundUnsupported] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                kind = message.get("type")
                message_id = message.get("id")
                sender = message.get("from")
                if kind in UNSUPPORTED_REPLY_KINDS and message_id and sender:
                    found.append(InboundUnsupported(message_id=message_id, sender=sender, kind=kind))
    return found


def normalize_recipient(number: str) -> str:
    if number.startswith("549") and len(number) == 13:
        return "54" + number[3:]
    return number


def make_graph_sender(access_token: str, phone_number_id: str, api_version: str):
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}

    async def send_text(to: str, text: str) -> None:
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalize_recipient(to),
            "type": "text",
            "text": {"body": text},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, json=body)
            if response.is_error:
                log.error("graph send failed status=%s body=%s", response.status_code, response.text[:500])
            response.raise_for_status()

    return send_text
