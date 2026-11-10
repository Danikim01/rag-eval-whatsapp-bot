import argparse
import json
from pathlib import Path
from typing import Callable

from modamayor.llm import build_generator
from modamayor.triage import triage

ROOT = Path(__file__).resolve().parent
TRIAGE_PATH = ROOT / "eval" / "triage_questions.json"
RESULTS_DIR = ROOT / "eval" / "results"


def load_questions() -> list[dict]:
    return json.loads(TRIAGE_PATH.read_text(encoding="utf-8"))["questions"]


def evaluate_triage(questions: list[dict], generate: Callable[[str], str]) -> list[dict]:
    results = []
    for q in questions:
        history = [(role, text) for role, text in q["history"]]
        got = triage(q["question"], history, generate)
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "expected": q["action"],
                "got": got,
                "passed": got == q["action"],
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="triage_v1")
    args = parser.parse_args()
    results = evaluate_triage(load_questions(), build_generator())
    for r in results:
        mark = "OK  " if r["passed"] else "FAIL"
        extra = "" if r["passed"] else f" expected={r['expected']} got={r['got']}"
        print(f"{mark} {r['id']} {r['question']!r}{extra}")
    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)}")
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.variant}.json"
    out.write_text(json.dumps({"variant": args.variant, "passed": passed, "total": len(results), "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
