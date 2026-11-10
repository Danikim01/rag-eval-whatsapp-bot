import re
from dataclasses import dataclass
from pathlib import Path

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

_FILE_MONTH = re.compile(r"([a-z]{3})(\d{4})")
_CHAT_LINE = re.compile(r"^\[(\d{2})/(\d{2})/(\d{4}) \d{2}:\d{2}\] (.*)$")


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    date: str | None = None


def _number(chunks: list[tuple[str, str | None]], source: str) -> list[Chunk]:
    return [Chunk(f"{source}#{i}", text, source, date) for i, (text, date) in enumerate(chunks)]


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    lines = text.strip().splitlines()
    title = lines[0].lstrip("# ").strip()
    sections = re.split(r"(?m)^## ", "\n".join(lines[1:]))
    parts = [
        f"{title}\n## {section.strip()}"
        for section in sections
        if section.strip()
    ]
    return _number([(p, None) for p in parts], source)


def _month_from_filename(source: str) -> str | None:
    match = _FILE_MONTH.search(source.lower())
    if not match or match.group(1) not in MONTHS:
        return None
    return f"{match.group(2)}-{MONTHS[match.group(1)]:02d}"


def chunk_pricelist(text: str, source: str) -> list[Chunk]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    header, body = blocks[0], blocks[1:]
    date = _month_from_filename(source)
    return _number([(f"{header}\n\n{b}", date) for b in body], source)


def chunk_chat(text: str, source: str) -> list[Chunk]:
    messages: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _CHAT_LINE.match(line)
        if match:
            day, month, year, body = match.groups()
            messages.append((f"{year}-{month}-{day}", body))
        elif messages:
            date, body = messages[-1]
            messages[-1] = (date, f"{body}\n{line}")
    return _number([(body, date) for date, body in messages], source)


def load_chunks(docs_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(docs_dir).iterdir()):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            chunks += chunk_markdown(text, path.name)
        elif path.name.startswith("chat_"):
            chunks += chunk_chat(text, path.name)
        elif path.name.startswith("lista_precios"):
            chunks += chunk_pricelist(text, path.name)
    return chunks
