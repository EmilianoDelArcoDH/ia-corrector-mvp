from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.content_extractor import build_content_base


FILENAME_PATTERN = re.compile(
    r"^(?P<module>[A-Za-z]+_\d+)\s*-\s*(?P<class_code>C\d+)\s*-\s*(?P<title>.+?)$"
)
ACTIVITY_PATTERN = re.compile(r"\bactividad\b", re.IGNORECASE)
PROJECT_PATTERN = re.compile(r"\bproyecto integrador\b", re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chunk and metadata files from PowerPoint classes.")
    parser.add_argument("--input-dir", default="data/clases", help="Directory with .pptx class materials.")
    parser.add_argument("--output-dir", default="data", help="Directory where generated JSON files will be written.")
    parser.add_argument(
        "--prefix",
        default="pptx_",
        help="Prefix for generated files so existing data files are not overwritten.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    prefix = args.prefix

    manifest = build_manifest(input_dir)
    content_base = build_content_base(manifest, base_dir=ROOT_DIR)
    classes_metadata = build_classes_metadata(content_base["class_catalog"], content_base["resources"])

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / f"{prefix}manifest.json", manifest)
    write_json(output_dir / f"{prefix}resources_metadata.json", content_base["resources"])
    write_json(output_dir / f"{prefix}chunks.json", content_base["chunks"])
    write_json(output_dir / f"{prefix}class_catalog.json", content_base["class_catalog"])
    write_json(output_dir / f"{prefix}classes_metadata.json", classes_metadata)

    print(
        f"Generated {len(manifest)} resources, {len(content_base['chunks'])} chunks and "
        f"{len(classes_metadata)} class metadata entries from {input_dir}."
    )


def build_manifest(input_dir: Path) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    absolute_input_dir = input_dir if input_dir.is_absolute() else (ROOT_DIR / input_dir)
    for file_path in sorted(absolute_input_dir.glob("*.pptx")):
        parsed = parse_filename(file_path)
        resource_id = f"{parsed['class_id']}-{slugify(parsed['title'])}-slides"
        resources.append(
            {
                "id": resource_id,
                "class_id": parsed["class_id"],
                "language": "data",
                "type": parsed["resource_type"],
                "title": parsed["title"],
                "source": "file",
                "path": file_path.relative_to(ROOT_DIR).as_posix(),
                "keywords": parsed["keywords"],
            }
        )
    return resources


def parse_filename(file_path: Path) -> dict[str, Any]:
    stem = file_path.stem.strip()
    match = FILENAME_PATTERN.match(stem)
    if match:
        module = match.group("module").lower().replace("_", "-")
        class_code = match.group("class_code").lower()
        title = clean_title(match.group("title"))
        class_id = f"{module}-{class_code}"
    else:
        module = "data-clases"
        class_code = "general"
        title = clean_title(stem)
        class_id = f"{module}-{slugify(title)[:24]}"

    resource_type = infer_resource_type(title)
    keywords = infer_keywords_from_title(title, module=module, class_code=class_code)
    return {
        "class_id": class_id,
        "title": title,
        "resource_type": resource_type,
        "keywords": keywords,
    }


def build_classes_metadata(class_catalog: list[dict[str, Any]], resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_class: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for resource in resources:
        key = (resource["class_id"], resource["language"])
        by_class.setdefault(key, []).append(resource)

    items: list[dict[str, Any]] = []
    for entry in class_catalog:
        key = (entry["class_id"], entry["language"])
        class_resources = by_class.get(key, [])
        preferred_title = pick_preferred_title(class_resources) or entry["class_id"]
        keywords = entry.get("keywords", [])[:12]
        learning_objectives = build_learning_objectives(keywords)
        items.append(
            {
                "class_id": entry["class_id"],
                "language": entry["language"],
                "title": preferred_title,
                "allowed_topics": keywords,
                "blocked_topics": [],
                "learning_objectives": learning_objectives,
                "common_errors": [],
                "source_titles": entry.get("resource_titles", []),
            }
        )
    return items


def pick_preferred_title(resources: list[dict[str, Any]]) -> str:
    ordered = sorted(resources, key=lambda item: (item.get("type") != "slides", item.get("title", "")))
    return ordered[0]["title"] if ordered else ""


def build_learning_objectives(keywords: list[str]) -> list[str]:
    if not keywords:
        return []
    return [f"Reconocer y aplicar conceptos vinculados con: {', '.join(keywords[:5])}."]


def infer_resource_type(title: str) -> str:
    if ACTIVITY_PATTERN.search(title):
        return "activity_slides"
    if PROJECT_PATTERN.search(title):
        return "project_slides"
    return "slides"


def infer_keywords_from_title(title: str, *, module: str, class_code: str) -> list[str]:
    tokens = [
        token
        for token in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", title.lower())
        if len(token) > 2 and token not in {"los", "las", "del", "para", "con", "sin", "una", "uno"}
    ]
    keywords: list[str] = []
    for value in [module, class_code.lower(), *tokens]:
        normalized = value.lower()
        if normalized not in keywords:
            keywords.append(normalized)
    return keywords[:12]


def clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip(" -")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "recurso"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
