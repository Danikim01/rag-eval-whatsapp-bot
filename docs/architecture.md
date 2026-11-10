# About the architecture

This page explains why the pipeline is built the way it is.
For commands and numbers, see [the eval reference](evals.md).

## Raw chunks failed on questions that span documents

The first version split the four shop documents into chunks and retrieved the closest ones with Chroma.
It passed most direct questions.
It failed the `multi-doc` type, where the answer needs a price list and a sales condition together, and the `contradiccion` type, where the June and October price lists disagree.
Raising k from 4 to 8 found more of the right sources (retrieval hits went from 19 to 21 of 23), yet the pass count stayed at 16.
More context did not help because the model still had to pick the current price from stale and fresh text side by side.

## Curated facts remove the stale text

`modamayor/curation.py` turns `modamayor/curated/facts.json` into chunks that each carry one fact.
Each price and rule in that file has a timeline of `from` dates, and `current_value` keeps only the entry in force on the `as_of` date that the eval question file declares.
The June price list never reaches the prompt for an October question.
This moved the score from 16 to 21 of 23 without changing the model.
The cost is that someone has to maintain `facts.json`. I think that is the right trade for a shop with a few dozen prices, and the wrong one for a corpus of thousands of pages.

## Arithmetic belongs to code

Even with the right facts in the prompt, a small local model makes mistakes when it adds line items or applies a quantity discount.
The `--quote` variant splits the work. The model extracts the order through the prompt from `build_order_prompt` in `modamayor/rag.py`, `parse_order` validates it, and `quote` in `modamayor/curation.py` computes the total.
That step took the `multi-doc` type from 2 of 4 to 4 of 4.

## Triage decides who answers

`modamayor/triage.py` classifies each message as `answer`, `clarify`, or `handoff` before retrieval runs.
A `handoff` reply contains a `wa.me` link to the owner, with the customer's question prefilled.
The pipeline does not notify the owner by itself, because the Cloud API gives a self-hosted bot no shared inbox. The link moves the conversation to a human at the cost of one tap from the customer.

## The webhook stays thin

`wabot/app.py` does four things before the pipeline sees a message.
It verifies the `X-Hub-Signature-256` HMAC, drops duplicate message ids through a SQLite store, takes a per-sender lock so replies keep their order, and loads the last six turns of history.
The reply runs in a background task, so the endpoint returns 200 to Meta immediately. A slow model call would otherwise trigger Meta's retries.

## One interface for three providers

`modamayor/llm.py` hides the generator and the embedder behind two plain callables.
Ollama is the default so that evals cost nothing to rerun. OpenAI and Anthropic are available through `LLM_PROVIDER` and `EMBED_PROVIDER`.
Anthropic offers no embeddings endpoint, so that provider supplies a generator only.
