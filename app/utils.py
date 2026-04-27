import json
import re
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9_.]+", value.lower()))


def combined_submission_content(files: Iterable[Any]) -> str:
    parts: list[str] = []
    for file in files:
        parts.append(format_submission_item(file))
    return "\n\n".join(parts)


def format_submission_item(item: Any) -> str:
    header = [f"# Entrega: {getattr(item, 'name', 'sin-nombre')}"]
    kind = getattr(item, "kind", None)
    if kind:
        header.append(f"tipo={getattr(kind, 'value', kind)}")
    mime_type = getattr(item, "mime_type", None)
    if mime_type:
        header.append(f"mime={mime_type}")

    body = extract_submission_text(item)
    return "\n".join([" | ".join(header), body])


def extract_submission_text(item: Any) -> str:
    content = getattr(item, "content", "") or ""
    if content.strip():
        return content.strip()

    url = getattr(item, "url", None)
    if not url:
        return ""

    fetched = fetch_url_text(url)
    if fetched:
        return fetched

    return url


def fetch_url_text(url: str) -> str:
    try:
        import httpx
    except ImportError:
        return ""

    if _is_google_spreadsheet_url(url):
        fetched_sheet = _fetch_google_spreadsheet_text(url, httpx)
        if fetched_sheet:
            return fetched_sheet

    for candidate_url in _url_candidates(url):
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                response = client.get(candidate_url)
                response.raise_for_status()
        except httpx.HTTPError:
            continue

        content_type = response.headers.get("content-type", "").lower()
        if "text/csv" in content_type or candidate_url.lower().endswith(".csv"):
            return response.text
        if "text/plain" in content_type or "application/json" in content_type:
            return response.text
        if "html" in content_type:
            return strip_html_tags(response.text)

        if response.text.strip():
            return response.text

    return ""


def _url_candidates(url: str) -> list[str]:
    candidates: list[str] = []
    parsed = urlparse(url)
    if "docs.google.com" not in parsed.netloc or "/spreadsheets/" not in parsed.path:
        return [url]

    path_match = re.search(r"/spreadsheets/d/([^/]+)", parsed.path)
    if not path_match:
        return [url]

    sheet_id = path_match.group(1)
    query = parse_qs(parsed.query)
    gid = query.get("gid", [None])[0]
    export_query = {"format": "csv"}
    if gid:
        export_query["gid"] = gid

    export_path = f"/spreadsheets/d/{sheet_id}/export"
    candidates.append(
        urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                export_path,
                "",
                urlencode(export_query),
                "",
            )
        )
    )

    candidates.append(
        urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                f"/spreadsheets/d/{sheet_id}/gviz/tq",
                "",
                urlencode({"tqx": "out:csv"}),
                "",
            )
        )
    )

    candidates.append(
        urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                f"/spreadsheets/d/{sheet_id}/pub",
                "",
                urlencode({"output": "csv"}),
                "",
            )
        )
    )

    candidates.append(url)
    return candidates


def _is_google_spreadsheet_url(url: str) -> bool:
    parsed = urlparse(url)
    return "docs.google.com" in parsed.netloc and "/spreadsheets/" in parsed.path


def _fetch_google_spreadsheet_text(url: str, httpx_module: Any) -> str:
    parsed = urlparse(url)
    path_match = re.search(r"/spreadsheets/d/([^/]+)", parsed.path)
    if not path_match:
        return ""

    sheet_id = path_match.group(1)
    base_url = urlunparse((parsed.scheme or "https", parsed.netloc, f"/spreadsheets/d/{sheet_id}/edit", "", "", ""))

    try:
        with httpx_module.Client(timeout=20.0, follow_redirects=True) as client:
            html_response = client.get(base_url)
            html_response.raise_for_status()
            sheet_names = _extract_google_sheet_names(html_response.text)
            if not sheet_names:
                sheet_names = ["Inicio"]

            sheet_texts: list[str] = []
            for sheet_name in sheet_names[:12]:
                csv_url = urlunparse(
                    (
                        parsed.scheme or "https",
                        parsed.netloc,
                        f"/spreadsheets/d/{sheet_id}/gviz/tq",
                        "",
                        urlencode({"tqx": "out:csv", "sheet": sheet_name}),
                        "",
                    )
                )
                csv_response = client.get(csv_url)
                csv_response.raise_for_status()
                content_type = csv_response.headers.get("content-type", "").lower()
                if "text/html" in content_type and _looks_like_google_login_page(csv_response.text):
                    continue
                text = csv_response.text.strip()
                if text:
                    sheet_texts.append(f"# Fuente: Google Sheets exportado\n# Hoja: {sheet_name}\n{text}")

            return "\n\n".join(sheet_texts)
    except httpx_module.HTTPError:
        return ""


def _extract_google_sheet_names(html_text: str) -> list[str]:
    names = [
        unescape(match).strip()
        for match in re.findall(r'docs-sheet-tab-caption">([^<]+)<', html_text)
        if unescape(match).strip()
    ]
    return list(dict.fromkeys(names))


def _looks_like_google_login_page(text: str) -> bool:
    lowered = text.lower()
    return "accede a tu cuenta de google" in lowered or "sign in" in lowered or "serviceLogin" in text


def strip_html_tags(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sanitize_blocked_topics(text: str, blocked_topics: Iterable[str]) -> str:
    sanitized = text
    for topic in blocked_topics:
        if not topic:
            continue
        pattern = re.compile(re.escape(topic), re.IGNORECASE)
        sanitized = pattern.sub("[tema no habilitado]", sanitized)
    return sanitized
