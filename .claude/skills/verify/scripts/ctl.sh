#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
RUN="$ROOT/verify-evidence/run"
PORT="${VERIFY_PORT:-8765}"
PIDFILE="$RUN/uvicorn.pid"
export VERIFY_DB="$RUN/wabot.db"
export VERIFY_OUTBOX="$RUN/outbox.jsonl"
export PYTHONPATH="$ROOT"

alive() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "${1:-}" in
  start)
    mkdir -p "$RUN"
    if alive; then echo "already running pid $(cat "$PIDFILE")"; exit 1; fi
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/webhook"; then echo "port $PORT is owned by another process"; exit 1; fi
    curl -sf http://localhost:11434/api/tags -o /dev/null || { echo "ollama is not reachable on 11434"; exit 1; }
    rm -f "$VERIFY_DB" "$VERIFY_OUTBOX"
    : > "$VERIFY_OUTBOX"
    setsid nohup .venv/bin/uvicorn offline_app:app --app-dir .claude/skills/verify/scripts --port "$PORT" > "$RUN/server.log" 2>&1 &
    echo $! > "$PIDFILE"
    for _ in $(seq 1 90); do
      code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/webhook?hub.mode=subscribe&hub.verify_token=verify-offline&hub.challenge=ok" || true)
      [ "$code" = "200" ] && { echo "ready pid $(cat "$PIDFILE") port $PORT"; exit 0; }
      alive || { echo "server died"; tail -n 20 "$RUN/server.log"; exit 1; }
      sleep 1
    done
    echo "timeout waiting for readiness"; tail -n 20 "$RUN/server.log"; exit 1
    ;;
  doctor)
    alive && echo "process: up pid $(cat "$PIDFILE")" || { echo "process: DOWN"; exit 1; }
    curl -sf http://localhost:11434/api/tags -o /dev/null && echo "ollama: up" || { echo "ollama: DOWN"; exit 1; }
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/webhook?hub.mode=subscribe&hub.verify_token=verify-offline&hub.challenge=ok")
    [ "$code" = "200" ] && echo "handshake: ok" || { echo "handshake: $code"; exit 1; }
    ;;
  stop)
    if alive; then kill "$(cat "$PIDFILE")"; fi
    rm -f "$PIDFILE"
    echo "stopped"
    ;;
  *)
    echo "usage: ctl.sh start|doctor|stop"; exit 2
    ;;
esac
