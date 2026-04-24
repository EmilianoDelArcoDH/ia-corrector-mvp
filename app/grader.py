import csv
import re
from io import StringIO
from typing import Any

from app.schemas import SubmittedFile
from app.utils import extract_submission_text


def grade_submission(language: str, files: list[SubmittedFile]) -> dict[str, Any]:
    normalized_language = language.lower()
    if normalized_language == "python":
        return grade_python(files)
    if normalized_language in {"html", "css", "js", "javascript"}:
        return grade_web(files)
    if normalized_language in {"sheet", "spreadsheet", "csv"}:
        return grade_sheet(files)

    return {
        "passed": False,
        "score": 0,
        "successes": [],
        "errors": [f"Lenguaje no soportado todavia: {language}"],
    }


def grade_python(files: list[SubmittedFile]) -> dict[str, Any]:
    python_files = [file for file in files if file.name.lower().endswith(".py")]
    selected_files = python_files or files
    code = "\n".join(extract_submission_text(file) for file in selected_files)
    compact = re.sub(r"\s+", "", code.lower())
    successes: list[str] = []
    errors: list[str] = []
    checks: list[bool] = []

    has_input = "input(" in code
    checks.append(has_input)
    _record(has_input, "Usa input() para solicitar datos.", "No se detecto uso de input().", successes, errors)

    has_strip = ".strip(" in code or ".strip()" in code
    checks.append(has_strip)
    _record(has_strip, "Limpia entradas con strip().", "No se detecto uso de strip().", successes, errors)

    has_isdigit = ".isdigit(" in code or ".isdigit()" in code
    checks.append(has_isdigit)
    _record(has_isdigit, "Valida numeros con isdigit().", "No se detecto validacion con isdigit().", successes, errors)

    has_if = re.search(r"^\s*if\b", code, flags=re.MULTILINE) is not None
    checks.append(has_if)
    _record(has_if, "Usa condicionales if.", "No se detecto una estructura if.", successes, errors)

    converts_without_validation = _converts_to_int_before_isdigit(code)
    checks.append(not converts_without_validation)
    _record(
        not converts_without_validation,
        "Evita convertir a int antes de validar.",
        "Convierte a int() antes de una validacion visible con isdigit().",
        successes,
        errors,
    )

    validates_empty = _has_empty_field_validation(code, compact)
    checks.append(validates_empty)
    _record(
        validates_empty,
        "Incluye validacion basica de campos vacios.",
        "No se detecto validacion basica de campos vacios.",
        successes,
        errors,
    )

    score = round(sum(checks) / len(checks) * 100)
    return {
        "passed": score >= 70 and not converts_without_validation,
        "score": score,
        "successes": successes,
        "errors": errors,
    }


def grade_web(files: list[SubmittedFile]) -> dict[str, Any]:
    html = "\n".join(
        extract_submission_text(file) for file in files if file.name.lower().endswith((".html", ".htm"))
    )
    all_content = "\n".join(extract_submission_text(file) for file in files)
    names = [file.name.lower() for file in files]
    successes: list[str] = []
    errors: list[str] = []
    checks: list[bool] = []

    web_checks = [
        (
            bool(re.search(r"<head\b[^>]*>", html, re.IGNORECASE)) and bool(re.search(r"</head>", html, re.IGNORECASE)),
            "Incluye etiqueta head con cierre.",
            "Falta la etiqueta head o su cierre.",
        ),
        (
            bool(re.search(r"<body\b[^>]*>", html, re.IGNORECASE)) and bool(re.search(r"</body>", html, re.IGNORECASE)),
            "Incluye etiqueta body con cierre.",
            "Falta la etiqueta body o su cierre.",
        ),
        (
            bool(re.search(r"<h[12]\b[^>]*>", html, re.IGNORECASE)),
            "Incluye un encabezado h1 o h2.",
            "No se detecto un encabezado h1 o h2.",
        ),
        (
            bool(re.search(r"<p\b[^>]*>", html, re.IGNORECASE)),
            "Incluye al menos un parrafo.",
            "No se detecto una etiqueta p.",
        ),
        (
            bool(re.search(r"<link\b[^>]*rel=[\"']?stylesheet", html, re.IGNORECASE))
            or any(name.endswith(".css") for name in names),
            'Usa CSS mediante link rel="stylesheet" o archivo .css.',
            "No se detecto CSS externo ni archivo .css.",
        ),
        (
            any(name.endswith(".js") for name in names) or bool(re.search(r"<script\b[^>]*src=", all_content, re.IGNORECASE)),
            "Incluye JavaScript mediante archivo .js o script con src.",
            "No se detecto archivo .js ni script con src.",
        ),
    ]

    for passed, success, error in web_checks:
        checks.append(passed)
        _record(passed, success, error, successes, errors)

    score = round(sum(checks) / len(checks) * 100)
    return {
        "passed": score >= 70,
        "score": score,
        "successes": successes,
        "errors": errors,
    }


def grade_sheet(files: list[SubmittedFile]) -> dict[str, Any]:
    sheet_text = "\n\n".join(
        extracted for extracted in (extract_submission_text(file) for file in files) if extracted.strip()
    )
    rows = _parse_table_rows(sheet_text)
    successes: list[str] = []
    errors: list[str] = []
    checks: list[bool] = []

    has_rows = len(rows) >= 2
    checks.append(has_rows)
    _record(
        has_rows,
        "La entrega incluye una tabla con datos.",
        "No se detectaron suficientes filas para evaluar la planilla.",
        successes,
        errors,
    )

    has_consistent_columns = _has_consistent_columns(rows)
    checks.append(has_consistent_columns)
    _record(
        has_consistent_columns,
        "Las filas mantienen una estructura de columnas razonable.",
        "La estructura de columnas se ve inconsistente o poco clara.",
        successes,
        errors,
    )

    has_header = _has_header_row(rows)
    checks.append(has_header)
    _record(
        has_header,
        "Se detecta una fila de encabezados.",
        "No se detecto una fila de encabezados clara.",
        successes,
        errors,
    )

    has_formula = any(cell.lstrip().startswith("=") for row in rows for cell in row)
    checks.append(has_formula)
    _record(
        has_formula,
        "Incluye al menos una formula o calculo.",
        "No se detecto ninguna formula en la planilla.",
        successes,
        errors,
    )

    has_nonempty_data = any(cell.strip() for row in rows[1:] for cell in row)
    checks.append(has_nonempty_data)
    _record(
        has_nonempty_data,
        "La planilla contiene datos cargados.",
        "No se detectaron datos mas alla del encabezado.",
        successes,
        errors,
    )

    score = round(sum(checks) / len(checks) * 100)
    return {
        "passed": score >= 70,
        "score": score,
        "successes": successes,
        "errors": errors,
    }


def _record(passed: bool, success: str, error: str, successes: list[str], errors: list[str]) -> None:
    if passed:
        successes.append(success)
    else:
        errors.append(error)


def _converts_to_int_before_isdigit(code: str) -> bool:
    int_match = re.search(r"\bint\s*\(", code)
    isdigit_match = re.search(r"\.isdigit\s*\(", code)
    if not int_match:
        return False
    if not isdigit_match:
        return True
    return int_match.start() < isdigit_match.start()


def _has_empty_field_validation(code: str, compact: str) -> bool:
    if re.search(r"if\s+not\s+[\w.()]+", code):
        return True
    empty_comparisons = [
        "==''",
        '==""',
        "!=''",
        '!="',
        "==none",
        "isnone",
    ]
    return any(pattern.lower() in compact for pattern in empty_comparisons)


def _parse_table_rows(text: str) -> list[list[str]]:
    if not text.strip():
        return []

    sample = text.strip().splitlines()[:10]
    delimiter = _detect_delimiter(sample)
    try:
        reader = csv.reader(StringIO(text), delimiter=delimiter)
        rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    except csv.Error:
        rows = []

    if rows:
        return rows

    fallback_rows: list[list[str]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in re.split(r"\t|;|,", line) if part.strip()]
        if parts:
            fallback_rows.append(parts)
    return fallback_rows


def _detect_delimiter(sample_lines: list[str]) -> str:
    joined = "\n".join(sample_lines)
    candidates = [",", ";", "\t", "|"]
    scored = [(joined.count(candidate), candidate) for candidate in candidates]
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else ","


def _has_consistent_columns(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    lengths = [len(row) for row in rows if row]
    if not lengths:
        return False
    most_common = max(set(lengths), key=lengths.count)
    return lengths.count(most_common) >= max(2, len(lengths) // 2)


def _has_header_row(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    first_row = rows[0]
    if not first_row:
        return False
    nonempty = [cell for cell in first_row if cell.strip()]
    if len(nonempty) < 2:
        return False
    return any(not _looks_numeric(cell) for cell in nonempty)


def _looks_numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[-+]?\d+([.,]\d+)?", value.strip()))
