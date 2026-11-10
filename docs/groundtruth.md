# Golden set for the FastAPI documentation

`groundtruth/golden_set.json` holds questions about the FastAPI documentation.
Each question points to chunk ids in one pinned revision of the docs.

The set is pinned to FastAPI commit `ba47d6d71b3e806900c8471f2f661781b8c43ec4`.
The documentation itself is not in this repository.

## Rebuild the corpus

1. Clone FastAPI into `data/fastapi`, which Git ignores.

	```
	git clone https://github.com/fastapi/fastapi data/fastapi
	git -C data/fastapi checkout ba47d6d71b3e806900c8471f2f661781b8c43ec4
	```

2. Validate the golden set.

	```
	.venv/bin/python groundtruth/validate_golden.py
	```

`groundtruth/loader.py` splits the English docs under `tutorial`, `advanced`, `deployment`, and `how-to` at level-3 headings.
The validator fails when the commit differs, an id repeats, or an evidence phrase is missing from its section.
It also checks that each question has an allowed category (`lookup`, `how-to`, `concept`, `gotcha`, `ambiguous`), difficulty, language, and verifier.
