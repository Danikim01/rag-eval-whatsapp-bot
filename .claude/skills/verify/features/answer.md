# Greeting and RAG answer

## Sub-features
- Greeting reply listing what the bot can help with.
- Price answer from the curated facts, with minimum units.
- Quote for an article and quantity, with the total computed by the `cotizar` tool.

## How to get to it (user POV)
The customer sends "Hola" or "Cuánto sale el buzo canguro?" on WhatsApp.

## Driving it with drive.py
Scenarios `greeting` and `price`. Proof: outbox reply contains "precios" for the greeting and the price 17.800 for the buzo canguro.

Scenarios `quote_total_from_code` and `order_never_confirmed` exercise the agent loop. Proof: the quote reply contains the code-computed total (213.600 cash or 196.512 transfer) and an order request is never answered with "confirmado" or "confirmamos".

## Gotchas
`ctl.sh` exports `WABOT_AGENT=1` by default so the offline app runs the tool loop; set `WABOT_AGENT=0` to drive the legacy path.
Triage may hand the order request off before the loop; `quote_total_from_code` is the scenario that proves `cotizar` runs.
Prices depend on `facts.json` and `WABOT_TODAY`; if facts change, update the check in `drive.py`.
