# Non-text messages

## Sub-features
- Audio, image, video and document messages get a code-built notice: only text is read, plus a `wa.me` link to the owner.
- Reactions, stickers and other types are ignored on purpose.
- The notice is deduplicated by message id and is never stored in `turns`.

## How to get to it (user POV)
- Send a voice note, photo, video or file to the bot number on WhatsApp.

## Driving it with drive.py
- The scenario `audio_gets_text_only_notice` posts a signed `type: audio` payload.
- Proof: one new outbox row containing "solo", "texto" and `wa.me/<OWNER>`, and the `turns` count unchanged.

## Gotchas
- Real media is never downloaded or transcribed, so the media id in the payload is a placeholder.
