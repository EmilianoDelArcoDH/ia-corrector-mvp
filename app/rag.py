from functools import lru_cache
from typing import Any

from app.utils import DATA_DIR, load_json, tokenize


@lru_cache(maxsize=1)
def load_classes_metadata() -> list[dict[str, Any]]:
    return load_json(DATA_DIR / "classes_metadata.json")


@lru_cache(maxsize=1)
def load_chunks() -> list[dict[str, Any]]:
    return load_json(DATA_DIR / "chunks.json")


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


# TODO: Replace keyword scoring with vector search when embeddings are introduced.
