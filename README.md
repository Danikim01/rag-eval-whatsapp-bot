# rag-eval-whatsapp-bot

A retrieval-augmented generation (RAG) pipeline for a small wholesale shop, with an eval harness that scores every change, served as a WhatsApp Cloud API webhook.

The shop ("Casa Beltran Mayorista"), its price lists, its sales conditions, and the owner chat are fictional.
No real business data is in this repository.

## What is in it

- `modamayor/` holds the RAG pipeline, the curated-facts retriever, the quote calculator, the triage step, and the eval runners.
- `wabot/` holds the FastAPI webhook that receives WhatsApp messages and replies with the pipeline.
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

	Expect 114 passed.

4. Run one eval.

	```
	.venv/bin/python -m modamayor.run_eval --variant curated_quote_k4 --chunks curated --quote
	```

## Documentation

- [Architecture](docs/architecture.md) explains why the pipeline has the parts it has.
- [Evals](docs/evals.md) lists the variants, the commands that regenerate each result, and the triage sets.
- [Webhook](docs/webhook.md) lists the environment variables, the endpoints, and the checks that run on each message.
- [Golden set](docs/groundtruth.md) explains how to rebuild the FastAPI documentation corpus and validate the golden set.

## License

[MIT](LICENSE).
