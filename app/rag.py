from functools import lru_cache
from typing import Any

from app.utils import DATA_DIR, load_json, tokenize


def _load_optional_json_files(filenames: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for filename in filenames:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        payload = load_json(path)
        if isinstance(payload, list):
            items.extend(payload)
    return items


@lru_cache(maxsize=1)
def load_classes_metadata() -> list[dict[str, Any]]:
    return _load_optional_json_files(["classes_metadata.json", "pptx_classes_metadata.json"])


@lru_cache(maxsize=1)
def load_chunks() -> list[dict[str, Any]]:
    return _load_optional_json_files(["chunks.json", "pptx_chunks.json"])


@lru_cache(maxsize=1)
def load_class_catalog() -> list[dict[str, Any]]:
    return _load_optional_json_files(["class_catalog.json", "pptx_class_catalog.json"])


def list_available_classes() -> list[dict[str, Any]]:
    catalog_by_key: dict[tuple[str, str], dict[str, Any]] = {
        (item["class_id"], item["language"].lower()): item for item in load_class_catalog()
    }

    classes: list[dict[str, Any]] = []
    for metadata in load_classes_metadata():
        key = (metadata["class_id"], metadata["language"].lower())
        summary = catalog_by_key.get(key, {})
        lesson_titles = list(
            dict.fromkeys(
                [
                    *summary.get("resource_titles", []),
                    *metadata.get("source_titles", []),
                ]
            )
        )
        classes.append(
            {
                "class_id": metadata["class_id"],
                "language": metadata["language"],
                "title": metadata.get("title", metadata["class_id"]),
                "resource_titles": lesson_titles,
                "resource_types": summary.get("resource_types", []),
                "allowed_topics": metadata.get("allowed_topics", []),
            }
        )

    classes.sort(key=lambda item: (item["language"] != "data", item["language"], item["class_id"]))
    return classes


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
