# Greeting and RAG answer

## Sub-features
- Greeting reply listing what the bot can help with.
- Price answer from the curated facts, with minimum units.

## How to get to it (user POV)
The customer sends "Hola" or "Cuánto sale el buzo canguro?" on WhatsApp.

## Driving it with drive.py
Scenarios `greeting` and `price`. Proof: outbox reply contains "precios" for the greeting and the price 17.800 for the buzo canguro.

## Gotchas
Prices depend on `facts.json` and `WABOT_TODAY`; if facts change, update the check in `drive.py`.
