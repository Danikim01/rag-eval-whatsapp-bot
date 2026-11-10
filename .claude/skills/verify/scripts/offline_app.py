import json
import os

from wabot.app import create_app
from wabot.config import Settings
from wabot.store import MessageStore

OUTBOX = os.environ["VERIFY_OUTBOX"]
DB = os.environ["VERIFY_DB"]

settings = Settings(
    verify_token="verify-offline",
    app_secret="secret-offline",
    access_token="unused-offline",
    phone_number_id="unused-offline",
    graph_api_version="v23.0",
    db_path=DB,
    owner_phone_number="5491100000000",
)


async def capture_sender(to: str, text: str) -> None:
    with open(OUTBOX, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"to": to, "text": text}, ensure_ascii=False) + "\n")


app = create_app(settings, sender=capture_sender, store=MessageStore(DB))
