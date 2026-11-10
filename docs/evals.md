# Eval reference

## Question sets

| File | Questions | Purpose |
|---|---|---|
| `modamayor/eval/questions.json` | 23 | Answer quality. Types: `directa` (10), `multi-doc` (4), `contradiccion` (6), `sin-respuesta` (3). |
| `modamayor/eval/triage_questions.json` | 14 | Triage action: `answer`, `clarify`, or `handoff`. |

`questions.json` declares an `as_of` date, `2026-11-09`.
The `--quote` variants and the curated chunks use that date as "today".

## Commands

Run each command from the repository root.
A run needs Ollama with `qwen3:8b` and `bge-m3`, unless you set `LLM_PROVIDER` or `EMBED_PROVIDER`.

| Variant | Command |
|---|---|
| Raw chunks | `python -m modamayor.run_eval --variant baseline_k4 --k 4` |
| Raw chunks, k=8 | `python -m modamayor.run_eval --variant baseline_k8 --k 8` |
| Curated facts | `python -m modamayor.run_eval --variant curated_k4 --chunks curated` |
| Curated facts and quote calculator | `python -m modamayor.run_eval --variant curated_quote_k4 --chunks curated --quote` |
| Full bot reply path | `python -m modamayor.run_eval --variant full_v4 --chunks curated --quote --full` |
| Triage | `python -m modamayor.run_triage --variant triage_v6` |

The `--full` flag sends each question through `modamayor.bot.reply`, so triage runs first.

## Result files

Each answer run writes `summary` with `passed`, `total`, `by_type`, and `retrieval_hits`.
`retrieval_hits` counts the questions whose expected source documents appear in the top k chunks.

| File | Passed | Retrieval hits |
|---|---|---|
| `baseline.json` | 17 of 23 | not recorded |
| `baseline_k4.json` | 16 of 23 | 19 |
| `baseline_k8.json` | 16 of 23 | 21 |
| `baseline_v2_k4.json` | 19 of 23 | 19 |
| `curated_k4.json` | 21 of 23 | 18 |
| `curated_quote_k4.json` | 22 of 23 | 18 |
| `curated_quote_k4_run1.json` to `_run3.json` | 22 of 23 each | 18 |
| `curated_quote_k4_v3.json` | 23 of 23 | 18 |
| `full_v1.json` | 21 of 23 | 18 |
| `full_v2.json`, `full_v3.json` | 23 of 23 each | 18 |

The three `curated_quote_k4_run` files use identical settings and give identical totals, so the three runs show no run-to-run variation in the pass count.
The files that end in `_v2` and `_v3`, and the `baseline.json` file, came from different scoring rules or prompts than their neighbors.
This repository does not record which, so do not read a difference between those files as the effect of one change.

## Triage results

| File | Passed |
|---|---|
| `triage_v1.json` to `triage_v3b.json` | 13 of 14 each |
| `triage_v4.json`, `triage_v4b.json`, `triage_v5_1.json`, `triage_v5_2.json` | 14 of 14 each |
| `triage_v2_unseen.json` | 26 of 26 |

The prompt was tuned against the 14 questions in `triage_questions.json`, so those scores are optimistic.
`triage_v2_unseen.json` holds 26 questions that the tuning never saw.
It scored 26 of 26 on prompt version 2, which is an earlier version than the one tuned to 14 of 14.
