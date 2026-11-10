import argparse
import json
from pathlib import Path
from typing import Callable

import chromadb

from modamayor.curation import build_chunks, load_facts
from modamayor.loader import load_chunks
from modamayor.bot import reply
from modamayor.llm import build_embedder, build_generator
from modamayor.rag import Retriever, answer
from modamayor.scoring import score

ROOT = Path(__file__).resolve().parent
QUESTIONS_PATH = ROOT / "eval" / "questions.json"
DOCS_DIR = ROOT / "docs"
FACTS_PATH = ROOT / "curated" / "facts.json"
RESULTS_DIR = ROOT / "eval" / "results"


def evaluate(questions: list[dict], answer_fn: Callable[[str], str]) -> list[dict]:
    results = []
    for q in questions:
        text = answer_fn(q["question"])
        s = score(q, text)
        results.append(
            {
                "id": q["id"],
                "type": q["type"],
                "question": q["question"],
                "answer": text,
                "passed": s.passed,
                "missing": s.missing,
                "forbidden_hits": s.forbidden_hits,
                "handoff_ok": s.handoff_ok,
            }
        )
    return results


def retrieval_report(questions: list[dict], retrieve_fn) -> list[dict]:
    report = []
    for q in questions:
        chunks = retrieve_fn(q)
        got = {c.source for c in chunks}
        missing = [s for s in q.get("sources", []) if s not in got]
        report.append(
            {
                "id": q["id"],
                "hit": not missing,
                "missing_sources": missing,
                "retrieved_ids": [c.id for c in chunks],
            }
        )
    return report


def summarize(results: list[dict]) -> dict:
    by_type: dict[str, list[int]] = {}
    for r in results:
        passed, total = by_type.setdefault(r["type"], [0, 0])
        by_type[r["type"]] = [passed + int(r["passed"]), total + 1]
    return {
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "by_type": by_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--chunks", choices=["raw", "curated"], default="raw")
    parser.add_argument("--quote", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    questions = payload["questions"]
    if args.chunks == "curated":
        chunks = build_chunks(load_facts(FACTS_PATH), payload["as_of"])
    else:
        chunks = load_chunks(DOCS_DIR)
    generate = build_generator()
    retriever = Retriever(chromadb.EphemeralClient(), build_embedder(), "modamayor", chunks)
    facts = load_facts(FACTS_PATH) if args.quote else None
    today = payload["as_of"] if args.quote else None
    if args.full:
        def respond(q: str) -> str:
            return reply(q, [], "5491100000000", retriever, generate, today=today, facts=facts, k=args.k)
    else:
        def respond(q: str) -> str:
            return answer(q, retriever, k=args.k, today=today, facts=facts, generate=generate)
    results = evaluate(questions, respond)
    summary = summarize(results)
    retrieval = retrieval_report(questions, lambda q: retriever.retrieve(q["question"], k=args.k))
    by_id = {r["id"]: r for r in retrieval}
    summary["retrieval_hits"] = sum(r["hit"] for r in retrieval)

    for r in results:
        mark = "OK  " if r["passed"] else "FAIL"
        detail = "" if r["passed"] else f" missing={r['missing']} forbidden={r['forbidden_hits']} handoff_ok={r['handoff_ok']}"
        ret = by_id[r["id"]]
        ret_mark = "" if ret["hit"] else f" RETRIEVAL_MISS={ret['missing_sources']}"
        print(f"{mark} {r['id']} [{r['type']}]{detail}{ret_mark}")
    print(f"\n{summary['passed']}/{summary['total']}  retrieval {summary['retrieval_hits']}/{summary['total']}")
    for kind, (passed, total) in summary["by_type"].items():
        print(f"  {kind}: {passed}/{total}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.variant}.json"
    out.write_text(
        json.dumps({"variant": args.variant, "k": args.k, "summary": summary, "results": results, "retrieval": retrieval},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
