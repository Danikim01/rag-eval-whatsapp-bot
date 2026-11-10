---
name: verify
description: Verify the wabot WhatsApp webhook (FastAPI plus the modamayor RAG on Ollama) by driving an isolated offline instance with signed Meta-shaped POSTs and reading the captured replies. Use before claiming any wabot or modamayor change works.
---

# Verify wabot

Surface: HTTP webhook (WhatsApp Cloud API shape) backed by the real RAG pipeline (Chroma, bge-m3, qwen3:8b via Ollama).
The offline instance uses the real `build_responder`, real SQLite history, real signature check.
Only the Graph sender is replaced by a capture sender that appends to an outbox JSONL.

## Isolation

The live instance (port 8000, connected to Meta through a cloudflared tunnel) must never be touched.
Verification runs on port 8765 with its own DB and secrets (`verify-offline`, `secret-offline`).
Never kill by process name, never use port 8000.

## Launch

```
.claude/skills/verify/scripts/ctl.sh start
```

Starts uvicorn on 8765 from an empty DB and empty outbox, builds the index, and returns only when the GET handshake answers 200 ("ready pid N port 8765").
Ollama must be up with `bge-m3` and `qwen3:8b`; the script refuses to start otherwise.
State lives in `verify-evidence/run/` (gitignored).

## Doctor

```
.claude/skills/verify/scripts/ctl.sh doctor
```

Read-only: process alive, Ollama reachable, handshake 200.

## Drive

```
PYTHONPATH=. .venv/bin/python .claude/skills/verify/scripts/drive.py
```

Run from the repo root.
Journeys, in one conversation: greeting, price question, off-domain clarify, second off-domain becomes handoff, custom-work handoff, duplicate message id ignored, history persisted.
Each step POSTs a signed payload, waits for the outbox entry, asserts on the reply text.
Exit code 0 means all PASS.
Per-feature detail: `features/README.md`.

## Evidence

Written to `verify-evidence/<timestamp>/`: `transcript.json` (ask, reply, seconds, ok), `turns.json` (SQLite history), `server.log`.
Proof standards: real HTTP path with valid HMAC, real model calls, side effects checked (outbox and DB rows), no test-only endpoints.
Replies come from a local LLM, so a FAIL on a reply check needs a re-run before concluding it is a regression; two failures in a row is real.

## Cleanup

```
.claude/skills/verify/scripts/ctl.sh stop
```

Kills only the PID in `verify-evidence/run/uvicorn.pid`.
`verify-evidence/<timestamp>/` is kept; `verify-evidence/run/` is scratch.

## Not covered

Real Graph delivery, token validity, and the tunnel are only verified with a real phone against the live instance.
