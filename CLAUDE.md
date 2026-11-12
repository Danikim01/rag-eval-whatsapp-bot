# Project notes

## Known Gotchas

- Business data stays out of git.
  `docs/privacidad.md` and `modamayor/docs/` are ignored.
- When the real Sistar `facts.json` arrives (step 4), ignore `modamayor/curated/facts.json` and untrack it with `git rm --cached`.
  Mount the real file into the container as a volume, because the Docker image needs `curated/facts.json` inside the package.
- `modamayor/triage.py` IDENTITY still names "Casa Beltrán Mayorista".
  Change it to Sistar when the real data arrives.
- `docs/privacidad.md` still says the AI providers are self-hosted.
  Update it before switching to Anthropic or OpenAI (step 3).
