from pathlib import Path

KB_DIR = Path(__file__).parent / "knowledge_base"

_cache: dict[str, tuple[float, str]] = {}


def _read(name: str) -> str:
    path = KB_DIR / f"{name}.md"
    if not path.exists():
        return ""
    mtime = path.stat().st_mtime
    cached = _cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]
    text = path.read_text(encoding="utf-8")
    _cache[name] = (mtime, text)
    return text


DEFAULT_KB_FILES = [
    "company_profile",
    "bernedette_bio",
    "case_studies",
    "rate_card",
    "boilerplate",
    "target_market",
    "standing_documents",
]


def load_kb(*names: str) -> str:
    """Load and concatenate knowledge_base markdown files, each under a ## heading."""
    files = names or DEFAULT_KB_FILES
    sections = []
    for name in files:
        text = _read(name)
        if text:
            title = name.replace("_", " ").title()
            sections.append(f"## {title}\n{text.strip()}")
    return "\n\n".join(sections)


def load_standing_documents() -> str:
    return _read("standing_documents")
