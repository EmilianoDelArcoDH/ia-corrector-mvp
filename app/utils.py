import json
import re
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9_.]+", value.lower()))


def combined_file_content(files: Iterable[Any]) -> str:
    return "\n\n".join(f"# Archivo: {file.name}\n{file.content}" for file in files)


def sanitize_blocked_topics(text: str, blocked_topics: Iterable[str]) -> str:
    sanitized = text
    for topic in blocked_topics:
        if not topic:
            continue
        pattern = re.compile(re.escape(topic), re.IGNORECASE)
        sanitized = pattern.sub("[tema no habilitado]", sanitized)
    return sanitized
