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
| `WABOT_DB_PATH` | no | `data/wabot.db` | SQLite file for message ids and history. |

The pipeline reads `LLM_PROVIDER` (`ollama`, `openai`, `anthropic`), `LLM_MODEL`, `EMBED_PROVIDER` (`ollama`, `openai`), `EMBED_MODEL`, and `OLLAMA_URL`.
`ollama` is the default for both providers, with `qwen3:8b` and `bge-m3` on `http://localhost:11434`.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/webhook` | Returns `hub.challenge` as plain text when `hub.mode` is `subscribe` and `hub.verify_token` matches. Otherwise returns 403. |
| `POST` | `/webhook` | Returns 403 when `X-Hub-Signature-256` does not match the HMAC SHA-256 of the body. Otherwise returns 200 and handles each message in a background task. |

Text messages go to the pipeline.
Other message types get a fixed reply that points the customer to the owner.
A message id that the SQLite store already holds is dropped.
Each sender has its own lock, so two quick messages from one customer are answered in order.
The prompt includes the last six turns of that sender's history.

## Check a running instance

The project `verify` skill drives an offline instance on port 8765 with a capture sender in place of the Graph API.
Read `.claude/skills/verify/SKILL.md`.
It needs Ollama running with both models, and it writes proof to `verify-evidence/`, which Git ignores.
