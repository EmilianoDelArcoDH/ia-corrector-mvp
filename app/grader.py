import re
from typing import Any

from app.schemas import SubmittedFile


def grade_submission(language: str, files: list[SubmittedFile]) -> dict[str, Any]:
    normalized_language = language.lower()
    if normalized_language == "python":
        return grade_python(files)
    if normalized_language in {"html", "css", "js", "javascript"}:
        return grade_web(files)

    return {
        "passed": False,
        "score": 0,
        "successes": [],
        "errors": [f"Lenguaje no soportado todavía: {language}"],
    }


def grade_python(files: list[SubmittedFile]) -> dict[str, Any]:
    python_files = [file for file in files if file.name.lower().endswith(".py")]
    selected_files = python_files or files
    code = "\n".join(file.content for file in selected_files)
    compact = re.sub(r"\s+", "", code.lower())
    successes: list[str] = []
    errors: list[str] = []
    checks: list[bool] = []

    has_input = "input(" in code
    checks.append(has_input)
    _record(checks[-1], "Usa input() para solicitar datos.", "No se detectó uso de input().", successes, errors)

    has_strip = ".strip(" in code or ".strip()" in code
    checks.append(has_strip)
    _record(checks[-1], "Limpia entradas con strip().", "No se detectó uso de strip() para limpiar espacios.", successes, errors)

    has_isdigit = ".isdigit(" in code or ".isdigit()" in code
    checks.append(has_isdigit)
    _record(checks[-1], "Valida números con isdigit().", "No se detectó uso de isdigit() para validar números.", successes, errors)

    has_if = re.search(r"^\s*if\b", code, flags=re.MULTILINE) is not None
    checks.append(has_if)
    _record(checks[-1], "Usa condicionales if.", "No se detectó una estructura if.", successes, errors)

    converts_without_validation = _converts_to_int_before_isdigit(code)
    checks.append(not converts_without_validation)
    _record(
        checks[-1],
        "Evita convertir a int antes de validar.",
        "Convierte a int() antes de una validación visible con isdigit().",
        successes,
        errors,
    )

    validates_empty = _has_empty_field_validation(code, compact)
    checks.append(validates_empty)
    _record(
        checks[-1],
        "Incluye validación básica de campos vacíos.",
        "No se detectó validación básica de campos vacíos.",
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
    html = "\n".join(file.content for file in files if file.name.lower().endswith((".html", ".htm")))
    all_content = "\n".join(file.content for file in files)
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
            "No se detectó un encabezado h1 o h2.",
        ),
        (
            bool(re.search(r"<p\b[^>]*>", html, re.IGNORECASE)),
            "Incluye al menos un párrafo.",
            "No se detectó una etiqueta p.",
        ),
        (
            bool(re.search(r"<link\b[^>]*rel=[\"']?stylesheet", html, re.IGNORECASE))
            or any(name.endswith(".css") for name in names),
            "Usa CSS mediante link rel=\"stylesheet\" o archivo .css.",
            "No se detectó CSS externo ni archivo .css.",
        ),
        (
            any(name.endswith(".js") for name in names) or bool(re.search(r"<script\b[^>]*src=", all_content, re.IGNORECASE)),
            "Incluye JavaScript mediante archivo .js o script con src.",
            "No se detectó archivo .js ni script con src.",
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
        '!=""',
        "==None",
        "isNone",
    ]
    return any(pattern.lower() in compact for pattern in empty_comparisons)
