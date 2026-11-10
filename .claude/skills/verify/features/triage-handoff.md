# Clarify then handoff

## Sub-features
- Off-domain question gets one clarify message.
- A second off-domain message becomes a handoff.
- Custom work requests go straight to handoff with a `wa.me` link.

## How to get to it (user POV)
Ask "De qué color es una naranja?", then "Y cuánto cuesta una naranja?", then "Hacen bordado con el logo de mi marca?".

## Driving it with drive.py
Scenarios `clarify`, `handoff_after_clarify`, `handoff_custom_work`. Proof: first reply contains "no te entendí bien", the next two contain "te paso con una persona" and `wa.me/5491100000000?text=`.

## Gotchas
Triage is an LLM call at temperature 0, but not guaranteed stable; re-run once before calling it a regression.
