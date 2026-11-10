# Webhook security

## Sub-features
- GET handshake with verify token.
- POST rejected without a valid HMAC signature.

## How to get to it (user POV)
Meta calls the endpoint; nobody else should be able to trigger replies.

## Driving it with drive.py
`ctl.sh start` already checks the handshake. Not yet driven: unsigned POST returning 403 and wrong verify token returning 403 (covered by `wabot/tests/test_webhook.py`).

## Gotchas
Offline secrets are `verify-offline` and `secret-offline`, never the real ones.
