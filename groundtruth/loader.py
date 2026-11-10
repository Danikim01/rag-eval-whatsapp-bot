import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

DOCS_DIR = Path(__file__).parent.parent / "data" / "fastapi" / "docs" / "en" / "docs"
COMMIT = "ba47d6d71b3e806900c8471f2f661781b8c43ec4"
SCOPE_DIRS = ("tutorial", "advanced", "deployment", "how-to")
SPLIT_LEVEL = 3
PREAMBLE_ANCHOR = "_preamble"
ANCHOR_RE = re.compile(r"\s*\{\s*#([\w-]+)\s*\}\s*$")


@dataclass
class Chunk:
    id: str
    file: str
    heading_path: list[str] = field(default_factory=list)
    text: str = ""
    commit: str = COMMIT


def split_title(raw):
    match = ANCHOR_RE.search(raw)
    if match:
        return raw[: match.start()].strip(), match.group(1)
    return raw.strip(), None


def slugify(title):
    return re.sub(r"[^\w]+", "-", title.lower()).strip("-")


def find_headings(text):
    tokens = MarkdownIt().parse(text)
    headings = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1:])
        if level <= SPLIT_LEVEL and token.map:
            title, anchor = split_title(tokens[index + 1].content)
            headings.append((level, title, anchor or slugify(title), token.map[0]))
    return headings


def load_markdown(path, root=DOCS_DIR):
    path = Path(path)
    file_id = path.relative_to(root).as_posix()
    lines = path.read_text(encoding="utf-8").split("\n")
    headings = find_headings("\n".join(lines))
    starts = [heading[3] for heading in headings] + [len(lines)]

    chunks = []
    preamble = "\n".join(lines[: starts[0]]).strip()
    if preamble:
        chunks.append(Chunk(f"{file_id}#{PREAMBLE_ANCHOR}", file_id, [], preamble))

    stack = []
    for position, (level, title, anchor, start) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        text = "\n".join(lines[start : starts[position + 1]]).strip()
        chunks.append(Chunk(f"{file_id}#{anchor}", file_id, [t for _, t in stack], text))
    return chunks


def load_corpus(root=DOCS_DIR):
    chunks = []
    for scope in SCOPE_DIRS:
        for path in sorted((root / scope).rglob("*.md")):
            chunks.extend(load_markdown(path, root))
    return chunks


def print_corpus_stats(chunks):
    ids = [chunk.id for chunk in chunks]
    sizes = sorted(len(chunk.text.split()) for chunk in chunks)
    duplicates = len(ids) - len(set(ids))
    print(f"files: {len({chunk.file for chunk in chunks})}, chunks: {len(chunks)}, duplicate ids: {duplicates}")
    print(
        f"words/chunk median: {statistics.median(sizes)}, "
        f"p90: {sizes[int(len(sizes) * 0.9)]}, p99: {sizes[int(len(sizes) * 0.99)]}, max: {sizes[-1]}"
    )
    print(f"chunks under 20 words: {sum(1 for size in sizes if size < 20)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for chunk in load_markdown(DOCS_DIR / sys.argv[1]):
            print(chunk.id, chunk.heading_path, len(chunk.text.split()))
    else:
        print_corpus_stats(load_corpus())
