# rag-eval-whatsapp-bot

A retrieval-augmented generation (RAG) pipeline for a small wholesale shop, with an eval harness that scores every change, served as a WhatsApp Cloud API webhook.

The shop in the corpus ("Casa Beltran Mayorista"), its price lists, its sales conditions, and the owner chat are fictional.
The only real business details in this repository are the contact data in [the privacy policy](docs/privacidad.md).
The bot is being prepared for production at the business Sistar, so the corpus will move to real data.

## What is in it

- `modamayor/` holds the RAG pipeline, the curated-facts retriever, the quote calculator, the triage step, and the eval runners.
- `wabot/` holds the FastAPI webhook that receives WhatsApp messages and replies with the pipeline.
  It stores each message in SQLite before it acknowledges Meta, so a crash does not lose a message.
- `Dockerfile`, `docker-compose.yml`, and `Caddyfile` run the webhook behind automatic HTTPS.
- `groundtruth/` holds a 2nd golden set, built from the FastAPI documentation, with a validator.
- `.claude/skills/verify/` holds a script that drives a running offline instance of the webhook.

## Results

The eval set has 23 questions in four types: `directa`, `multi-doc`, `contradiccion`, and `sin-respuesta`.
Each row below is a committed file in `modamayor/eval/results/`.

| Variant | File | Passed |
|---|---|---|
| Raw chunks, k=4 | `baseline_k4.json` | 16 of 23 |
| Raw chunks, k=8 | `baseline_k8.json` | 16 of 23 |
| Curated facts, k=4 | `curated_k4.json` | 21 of 23 |
| Curated facts and quote calculator, k=4 | `curated_quote_k4_v3.json` | 23 of 23 |
| Full bot reply path, k=4 | `full_v3.json` | 23 of 23 |

Result files were produced during development, and the scoring and prompts changed between some of them.
Read [the eval reference](docs/evals.md) before you compare two rows.

## Quickstart

You need Python 3.12 or later and [Ollama](https://ollama.com) running locally.

1. Pull the two default models.

	```
	ollama pull qwen3:8b
	ollama pull bge-m3
	```

2. Install the dependencies.

	```
	python -m venv .venv
	.venv/bin/pip install -e . pytest
	```

3. Run the tests. They need no network and no Ollama.

	```
	.venv/bin/python -m pytest -q
	```

	Expect 136 passed.

4. Run one eval.

	```
	.venv/bin/python -m modamayor.run_eval --variant curated_quote_k4 --chunks curated --quote
	```

## Run with Docker

The compose file starts the webhook and Caddy.
Caddy gets a TLS certificate for your domain and proxies only `/webhook` and `/health`.
Every other path returns 404.

1. Point a DNS record for your domain at the server.
2. Copy `wabot/.env.example` to `.env` in the repository root and fill in every value, including `DOMAIN`.
3. Start the stack.

	```
	docker compose up -d --build
	```

4. Check the webhook.

	```
	curl https://$DOMAIN/health
	```

	The response is `{"status": "ok"}`.

The SQLite database lives in the `wabot-data` volume, so it survives a rebuild.
The webhook needs a model provider.
By default it reaches Ollama on the host through `OLLAMA_URL`.
Ollama listens only on `127.0.0.1` by default, and a container cannot reach that address.
On a server, set `LLM_PROVIDER`, `LLM_MODEL`, `EMBED_PROVIDER`, and `EMBED_MODEL` to an API provider instead.
Run a single webhook process, because the per-sender locks and the retry queue live in memory.

## Documentation

- [Architecture](docs/architecture.md) explains why the pipeline has the parts it has.
- [Evals](docs/evals.md) lists the variants, the commands that regenerate each result, and the triage sets.
- [Webhook](docs/webhook.md) lists the environment variables, the endpoints, the delivery guarantees, and the checks that run on each message.
- [Golden set](docs/groundtruth.md) explains how to rebuild the FastAPI documentation corpus and validate the golden set.

## License

[MIT](LICENSE).
