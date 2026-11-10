import hashlib
import hmac
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from modamayor.scoring import HANDOFF_MARKER
from modamayor.triage import CLARIFY_MARKER

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / "verify-evidence" / "run"
OUTBOX = RUN / "outbox.jsonl"
DB = RUN / "wabot.db"
URL = "http://127.0.0.1:8765/webhook"
SECRET = "secret-offline"
SENDER = "5491155550001"
OWNER = "5491100000000"

SCENARIOS = [
    ("greeting", "Hola", lambda r: "precios" in r.lower()),
    ("price", "Cuánto sale el buzo canguro?", lambda r: "17.800" in r or "17800" in r),
    ("clarify", "De qué color es una naranja?", lambda r: CLARIFY_MARKER in r),
    ("handoff_after_clarify", "Y cuánto cuesta una naranja?", lambda r: HANDOFF_MARKER in r and f"wa.me/{OWNER}?text=" in r),
    ("handoff_custom_work", "Hacen bordado con el logo de mi marca?", lambda r: HANDOFF_MARKER in r and f"wa.me/{OWNER}?text=" in r),
]


def payload(message_id: str, text: str, kind: str = "text") -> bytes:
    message = {"from": SENDER, "id": message_id, "type": kind}
    message.update({"text": {"body": text}} if kind == "text" else {kind: {"id": "MEDIA1", "mime_type": "audio/ogg"}})
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    message
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()


def post(body: bytes) -> int:
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(URL, data=body, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def outbox() -> list[dict]:
    return [json.loads(line) for line in OUTBOX.read_text(encoding="utf-8").splitlines() if line]


def wait_for(count: int, timeout: float = 90) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = outbox()
        if len(rows) >= count:
            return rows
        time.sleep(0.5)
    raise SystemExit(f"timeout waiting for reply #{count}")


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "verify-evidence" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript = []
    failures = 0
    for index, (name, text, check) in enumerate(SCENARIOS, start=1):
        started = time.time()
        status = post(payload(f"wamid.verify.{stamp}.{index}", text))
        rows = wait_for(index)
        reply = rows[index - 1]["text"]
        ok = status == 200 and rows[index - 1]["to"] == SENDER and check(reply)
        failures += not ok
        transcript.append({"scenario": name, "ask": text, "reply": reply, "seconds": round(time.time() - started, 1), "ok": ok})
        print(f"{'PASS' if ok else 'FAIL'} {name} ({transcript[-1]['seconds']}s)")

    post(payload(f"wamid.verify.{stamp}.1", SCENARIOS[0][1]))
    time.sleep(3)
    dedup_ok = len(outbox()) == len(SCENARIOS)
    failures += not dedup_ok
    print(f"{'PASS' if dedup_ok else 'FAIL'} duplicate_message_id_not_answered_twice")

    with sqlite3.connect(DB) as conn:
        turns = conn.execute("SELECT role, text FROM turns WHERE wa_id = ? ORDER BY id", (SENDER,)).fetchall()
    history_ok = len(turns) == 2 * len(SCENARIOS) and [r for r, _ in turns[:2]] == ["user", "assistant"]
    failures += not history_ok
    print(f"{'PASS' if history_ok else 'FAIL'} history_persisted turns={len(turns)}")

    started = time.time()
    status = post(payload(f"wamid.verify.{stamp}.audio", "", kind="audio"))
    rows = wait_for(len(SCENARIOS) + 1)
    notice = rows[-1]["text"]
    with sqlite3.connect(DB) as conn:
        turns_after = conn.execute("SELECT COUNT(*) FROM turns WHERE wa_id = ?", (SENDER,)).fetchone()[0]
    audio_ok = status == 200 and "solo" in notice and "texto" in notice and f"wa.me/{OWNER}" in notice and turns_after == len(turns)
    failures += not audio_ok
    transcript.append({"scenario": "audio_gets_text_only_notice", "ask": "<audio>", "reply": notice, "seconds": round(time.time() - started, 1), "ok": audio_ok})
    print(f"{'PASS' if audio_ok else 'FAIL'} audio_gets_text_only_notice")

    base = len(SCENARIOS) + 1
    statuses = [post(payload(f"wamid.verify.{stamp}.burst{i}", t)) for i, t in enumerate(["Hola", "Cuánto sale el buzo canguro?"])]
    wait_for(base + 2)
    with sqlite3.connect(DB) as conn:
        burst = conn.execute("SELECT role FROM turns WHERE wa_id = ? ORDER BY id", (SENDER,)).fetchall()[len(turns):]
    burst_ok = statuses == [200, 200] and [r for (r,) in burst] == ["user", "assistant"] * 2
    failures += not burst_ok
    transcript.append({"scenario": "same_sender_burst_ordered", "ask": "<2 rapid messages>", "reply": str(burst), "seconds": 0, "ok": burst_ok})
    print(f"{'PASS' if burst_ok else 'FAIL'} same_sender_burst_ordered")

    (out_dir / "transcript.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "turns.json").write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")
    server_log = RUN / "server.log"
    if server_log.exists():
        (out_dir / "server.log").write_text(server_log.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"evidence: {out_dir.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
