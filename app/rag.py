from functools import lru_cache
from typing import Any

from app.utils import DATA_DIR, load_json, tokenize


@lru_cache(maxsize=1)
def load_classes_metadata() -> list[dict[str, Any]]:
    return load_json(DATA_DIR / "classes_metadata.json")


@lru_cache(maxsize=1)
def load_chunks() -> list[dict[str, Any]]:
    return load_json(DATA_DIR / "chunks.json")


@lru_cache(maxsize=1)
def load_class_catalog() -> list[dict[str, Any]]:
    path = DATA_DIR / "class_catalog.json"
    if not path.exists():
        return []
    return load_json(path)


def get_class_metadata(class_id: str, language: str) -> dict[str, Any] | None:
    normalized_language = language.lower()
    for item in load_classes_metadata():
        if item["class_id"] == class_id and item["language"].lower() == normalized_language:
            return item
    return None


def search_chunks(
    *,
    class_id: str,
    language: str,
    query: str,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    normalized_language = language.lower()
    scored_chunks: list[tuple[int, dict[str, Any]]] = []

    for chunk in load_chunks():
        if chunk["class_id"] != class_id:
            continue
        if chunk["language"].lower() != normalized_language:
            continue

        searchable_text = " ".join(
            [
                chunk.get("title", ""),
                chunk.get("content", ""),
                " ".join(chunk.get("keywords", [])),
            ]
        )
        chunk_tokens = tokenize(searchable_text)
        keyword_tokens = tokenize(" ".join(chunk.get("keywords", [])))
        score = len(query_tokens & chunk_tokens) + len(query_tokens & keyword_tokens)

        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:top_k]]


def get_class_content_summary(class_id: str, language: str) -> dict[str, Any]:
    normalized_language = language.lower()
    for item in load_class_catalog():
        if item["class_id"] == class_id and item["language"].lower() == normalized_language:
            return item
    return {
        "class_id": class_id,
        "language": language,
        "resource_ids": [],
        "resource_titles": [],
        "resource_types": [],
        "keywords": [],
    }


# TODO: Replace keyword scoring with vector search when embeddings are introduced.
