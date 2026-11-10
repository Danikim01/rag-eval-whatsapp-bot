import re
import unicodedata
from dataclasses import dataclass, field

HANDOFF_MARKER = "te paso con una persona"

_THOUSANDS = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")


def normalize(text: str) -> str:
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )
    return _THOUSANDS.sub("", stripped.lower())


@dataclass
class Score:
    passed: bool
    missing: list[str] = field(default_factory=list)
    forbidden_hits: list[str] = field(default_factory=list)
    handoff_ok: bool = True


def score(question: dict, answer: str) -> Score:
    text = normalize(answer)
    missing = [f for f in question.get("key_facts", []) if normalize(f) not in text]
    forbidden = [f for f in question.get("must_not_say", []) if normalize(f) in text]
    handoff_ok = (HANDOFF_MARKER in text) == bool(question.get("handoff"))
    passed = not missing and not forbidden and handoff_ok
    return Score(passed=passed, missing=missing, forbidden_hits=forbidden, handoff_ok=handoff_ok)
