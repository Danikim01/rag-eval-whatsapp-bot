import json
import sys
from collections import Counter
from pathlib import Path

from loader import COMMIT, load_corpus

GOLDEN_PATH = Path(__file__).parent / "golden_set.json"
CATEGORIES = {"lookup", "how-to", "concept", "gotcha", "ambiguous"}
DIFFICULTIES = {"easy", "medium", "hard"}
LANGS = {"en", "es"}
VERIFIERS = {"daniel", "model"}


def normalize(text):
    for mark in ("**", "`"):
        text = text.replace(mark, "")
    return " ".join(text.split())


def validate(golden, chunks):
    by_id = {chunk.id: normalize(chunk.text) for chunk in chunks}
    errors = []
    if golden["commit"] != COMMIT:
        errors.append(f"commit mismatch: {golden['commit']} != {COMMIT}")
    seen = set()
    for item in golden["questions"]:
        qid = item["id"]
        if qid in seen:
            errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        if item["category"] not in CATEGORIES:
            errors.append(f"{qid}: bad category {item['category']}")
        if item["difficulty"] not in DIFFICULTIES:
            errors.append(f"{qid}: bad difficulty {item['difficulty']}")
        if item["lang"] not in LANGS:
            errors.append(f"{qid}: bad lang {item['lang']}")
        if item.get("verified_by") not in VERIFIERS:
            errors.append(f"{qid}: bad verified_by {item.get('verified_by')}")
        if not item["expected"]:
            errors.append(f"{qid}: no expected sections")
        for target in item["expected"]:
            text = by_id.get(target["id"])
            if text is None:
                errors.append(f"{qid}: unknown section {target['id']}")
            else:
                phrases = target["evidence"]
                if isinstance(phrases, str):
                    phrases = [phrases]
                for phrase in phrases:
                    if normalize(phrase) not in text:
                        errors.append(f"{qid}: evidence not found in {target['id']}: {phrase!r}")
    return errors


def print_distribution(golden):
    questions = golden["questions"]
    print(f"questions: {len(questions)}")
    for key in ("category", "difficulty", "lang", "verified_by"):
        print(f"{key}: {dict(Counter(item[key] for item in questions))}")
    files = Counter(target["id"].split("#")[0] for item in questions for target in item["expected"])
    sections = Counter(target["id"] for item in questions for target in item["expected"])
    print(f"files: {dict(files)}")
    print(f"max questions on one section: {max(sections.values())}")
    for section, count in sections.items():
        if count > 3:
            print(f"WARN {section} has {count} questions")


if __name__ == "__main__":
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    errors = validate(golden, load_corpus())
    print_distribution(golden)
    for error in errors:
        print("ERROR", error)
    sys.exit(1 if errors else 0)
