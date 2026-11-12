import asyncio
import hmac
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response

from wabot.config import Settings
from wabot.store import MessageStore
from modamayor.triage import text_only_message
from wabot.whatsapp import (
    InboundText,
    InboundUnsupported,
    extract_text_messages,
    extract_unsupported_messages,
    make_graph_sender,
    verify_signature,
)

log = logging.getLogger("wabot")

Sender = Callable[[str, str], Awaitable[None]]
Responder = Callable[[str, list[tuple[str, str]]], str]

HISTORY_TURNS = 6
MAX_ATTEMPTS = 3
RETENTION_DAYS = 365
MAX_TURNS_PER_SENDER = 200
MAX_PENDING_AGE_HOURS = 24


def create_app(
    settings: Settings | None = None,
    sender: Sender | None = None,
    store: MessageStore | None = None,
    responder: Responder | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or MessageStore(settings.db_path)
    sender = sender or make_graph_sender(settings.access_token, settings.phone_number_id, settings.graph_api_version)
    if responder is None:
        from wabot.rag_responder import build_responder

        responder = build_responder(settings.owner_phone_number)
    in_flight: set[str] = set()
    chat_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def handle(message: InboundText) -> None:
        if message.message_id in in_flight or store.is_done(message.message_id):
            log.info("duplicate message_id=%s", message.message_id)
            return
        in_flight.add(message.message_id)
        try:
            async with chat_locks[message.sender]:
                try:
                    history = store.recent(message.sender, HISTORY_TURNS)
                    text = await asyncio.to_thread(responder, message.text, history)
                    await sender(message.sender, text)
                    store.complete(message.message_id, message.sender, message.text, text)
                except Exception:
                    store.record_failure(message.message_id, MAX_ATTEMPTS)
                    log.exception("reply failed message_id=%s", message.message_id)
                    return
            log.info("replied message_id=%s", message.message_id)
        finally:
            in_flight.discard(message.message_id)

    async def recover() -> None:
        store.prune(RETENTION_DAYS, MAX_TURNS_PER_SENDER)
        pending = store.pending(MAX_PENDING_AGE_HOURS)
        if pending:
            log.info("recovering pending=%d", len(pending))
        await asyncio.gather(*(handle(InboundText(m, w, t)) for m, w, t in pending))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(recover())
        yield
        await task

    app = FastAPI(lifespan=lifespan)

    async def handle_unsupported(message: InboundUnsupported) -> None:
        if not store.claim(message.message_id):
            log.info("duplicate message_id=%s", message.message_id)
            return
        try:
            await sender(message.sender, text_only_message(settings.owner_phone_number))
        except Exception:
            store.release(message.message_id)
            log.exception("unsupported reply failed message_id=%s kind=%s", message.message_id, message.kind)
            return
        log.info("replied unsupported message_id=%s kind=%s", message.message_id, message.kind)

    @app.get("/health")
    async def health() -> Response:
        try:
            await asyncio.to_thread(store.ping)
        except Exception:
            log.exception("health check failed")
            return Response(content='{"status": "unavailable"}', status_code=503, media_type="application/json")
        return Response(content='{"status": "ok"}', media_type="application/json")

    @app.get("/webhook")
    async def verify(
        mode: str | None = Query(None, alias="hub.mode"),
        token: str | None = Query(None, alias="hub.verify_token"),
        challenge: str | None = Query(None, alias="hub.challenge"),
    ) -> Response:
        if mode == "subscribe" and token and hmac.compare_digest(token, settings.verify_token):
            return Response(content=challenge or "", media_type="text/plain")
        raise HTTPException(status_code=403)

    @app.post("/webhook")
    async def receive(request: Request, background: BackgroundTasks) -> Response:
        body = await request.body()
        if not verify_signature(settings.app_secret, body, request.headers.get("X-Hub-Signature-256")):
            raise HTTPException(status_code=403)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            log.warning("invalid json with valid signature")
            return Response(status_code=200)
        for message in extract_text_messages(payload):
            store.enqueue(message.message_id, message.sender, message.text)
            background.add_task(handle, message)
        for unsupported in extract_unsupported_messages(payload):
            background.add_task(handle_unsupported, unsupported)
        return Response(status_code=200)

    return app
