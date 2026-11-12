# Webhook reference

`wabot/main.py` exposes `app`, a FastAPI application.

```
.venv/bin/uvicorn wabot.main:app --port 8000
```

## Environment variables

`wabot/config.py` reads these at startup and loads a `.env` file if one exists.
Copy `wabot/.env.example` to `.env` and fill in the values. Never commit `.env`.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `WA_VERIFY_TOKEN` | yes | none | Token that Meta sends in the handshake. You choose it. |
| `WA_APP_SECRET` | yes | none | App secret that signs each POST. |
| `WA_ACCESS_TOKEN` | yes | none | Token for the Graph API send call. |
| `WA_PHONE_NUMBER_ID` | yes | none | ID of the sending phone number. |
| `OWNER_PHONE_NUMBER` | yes | none | Digits only. Target of the `wa.me` handoff link. |
| `WA_GRAPH_API_VERSION` | no | `v23.0` | Graph API version in the send URL. |
| `WABOT_DB_PATH` | no | `data/wabot.db` | SQLite file for the message inbox and history. |
| `DOMAIN` | Docker only | none | Public host name that Caddy serves. |

The pipeline reads `LLM_PROVIDER` (`ollama`, `openai`, `anthropic`), `LLM_MODEL`, `EMBED_PROVIDER` (`ollama`, `openai`), `EMBED_MODEL`, and `OLLAMA_URL`.
`ollama` is the default for both providers, with `qwen3:8b` and `bge-m3` on `http://localhost:11434`.
The compose file sets `OLLAMA_URL` to `http://host.docker.internal:11434`.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/webhook` | Returns `hub.challenge` as plain text when `hub.mode` is `subscribe` and `hub.verify_token` matches. Otherwise returns 403. |
| `GET` | `/health` | Returns 200 with `{"status": "ok"}` when the database answers a query. Returns 503 with `{"status": "unavailable"}` otherwise. The body never includes error details. |
| `POST` | `/webhook` | Returns 403 when `X-Hub-Signature-256` does not match the HMAC SHA-256 of the body. Otherwise saves each text message to the inbox, returns 200, and handles the message in a background task. |

Text messages go to the pipeline.
Other message types get a fixed reply that points the customer to the owner.
A message id that the store already marks as done, or that is being handled, is dropped.
Each sender has its own lock, so two quick messages from one customer are answered in order.
The prompt includes the last six turns of that sender's history.

## Delivery guarantees

The webhook saves a text message to the `inbox` table before it returns 200.
Delivery is at least once: a crash after the reply and before the save can send one reply twice.
A failed reply counts one attempt.
After 3 attempts the message stops retrying.
On startup the webhook handles every message that is still pending and younger than 24 hours.
The same startup step deletes turns older than 365 days and keeps at most 200 turns per sender.
Run one process only, because the locks and the in-flight set live in memory.

## Run in Docker

`Dockerfile` builds the image and runs `uvicorn` with one worker as the non-root user `wabot`.
The image has a `HEALTHCHECK` on `/health`.
`docker-compose.yml` adds Caddy, which serves `DOMAIN` over HTTPS and forwards `/webhook` and `/health` only.
The `wabot-data` volume holds `/data/wabot.db`.
Logs go to standard output and do not include tokens or secrets.

## Check a running instance

The project `verify` skill drives an offline instance on port 8765 with a capture sender in place of the Graph API.
Read `.claude/skills/verify/SKILL.md`.
It needs Ollama running with both models, and it writes proof to `verify-evidence/`, which Git ignores.
