# Conversation history and dedup

## Sub-features
- Each exchange stores a user and an assistant turn in SQLite.
- A repeated message id is not answered twice.

## How to get to it (user POV)
Meta retries deliveries; the customer sees one reply.

## Driving it with drive.py
Step `duplicate_message_id_not_answered_twice` re-POSTs the first id and checks the outbox count is unchanged; step `history_persisted` checks the `turns` table.

## Gotchas
The outbox is shared across the run, so the dedup check assumes it runs after the scenarios.
