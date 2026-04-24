from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.content_extractor import build_content_base, load_source_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build content metadata and chunk index from a manifest.")
    parser.add_argument("--manifest", required=True, help="Path to a JSON manifest with content sources.")
    parser.add_argument("--output-dir", default="data", help="Directory where the generated JSON files will be written.")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Base directory for relative file paths declared in the manifest.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    base_dir = Path(args.base_dir)

    sources = load_source_manifest(manifest_path)
    content_base = build_content_base(sources, base_dir=base_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "resources_metadata.json").write_text(
        json.dumps(content_base["resources"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "chunks.json").write_text(
        json.dumps(content_base["chunks"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "class_catalog.json").write_text(
        json.dumps(content_base["class_catalog"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Generated {len(content_base['resources'])} resources, {len(content_base['chunks'])} chunks and "
        f"{len(content_base['class_catalog'])} class entries."
    )


if __name__ == "__main__":
    main()
