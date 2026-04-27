import os
from typing import Any

import httpx
from fastapi import HTTPException

from app.utils import sanitize_blocked_topics


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "220"))


def build_prompt(
    *,
    mode: str,
    language: str,
    class_metadata: dict[str, Any],
    class_content_summary: dict[str, Any],
    grader_result: dict[str, Any],
    context_chunks: list[dict[str, Any]],
) -> str:
    blocked_topics = class_metadata.get("blocked_topics", [])
    mode_instructions = _mode_instructions(mode)
    context = "\n".join(f"- {chunk.get('title')}: {chunk.get('content')}" for chunk in context_chunks)
    if not context:
        context = "- No se recupero contexto especifico."

    return f"""
Sos un asistente pedagogico para correccion educativa.

Reglas obligatorias:
- Primero respeta el resultado del corrector objetivo. No inventes errores ni aciertos.
- No des una solucion completa ni codigo completo.
- No uses ni recomiendes estos temas bloqueados: {", ".join(blocked_topics)}.
- Si un tema bloqueado parece util, omitilo y reformula con los temas permitidos.
- Redacta en espanol claro, con tono docente y concreto.

Modo de correccion: {mode}
Instrucciones del modo:
{mode_instructions}

Lenguaje: {language}
Clase: {class_metadata.get("title")}
Temas permitidos: {", ".join(class_metadata.get("allowed_topics", []))}
Temas bloqueados: {", ".join(blocked_topics)}
Objetivos de aprendizaje:
{_bullet_list(class_metadata.get("learning_objectives", []))}

Contenido de la clase:
- Recursos: {_bullet_list(class_content_summary.get("resource_titles", []))}
- Tipos de recurso: {_bullet_list(class_content_summary.get("resource_types", []))}
- Palabras clave: {", ".join(class_content_summary.get("keywords", [])) or "Ninguna."}

Resultado objetivo:
- Aprobado: {grader_result.get("passed")}
- Puntaje: {grader_result.get("score")}
- Aciertos:
{_bullet_list(grader_result.get("successes", []))}
- Errores:
{_bullet_list(grader_result.get("errors", []))}

Contexto recuperado:
{context}

Escribi una devolucion breve y util. Debe mencionar primero lo logrado y luego lo pendiente.
""".strip()


async def generate_feedback(
    *,
    mode: str,
    language: str,
    class_metadata: dict[str, Any],
    class_content_summary: dict[str, Any],
    grader_result: dict[str, Any],
    context_chunks: list[dict[str, Any]],
) -> str:
    prompt = build_prompt(
        mode=mode,
        language=language,
        class_metadata=class_metadata,
        class_content_summary=class_content_summary,
        grader_result=grader_result,
        context_chunks=context_chunks,
    )
    payload = {
        "model": os.getenv("OLLAMA_MODEL", OLLAMA_MODEL),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", str(OLLAMA_NUM_PREDICT))),
        },
    }

    try:
        async with httpx.AsyncClient(
            timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", str(OLLAMA_TIMEOUT_SECONDS)))
        ) as client:
            response = await client.post(
                f"{os.getenv('OLLAMA_URL', OLLAMA_URL).rstrip('/')}/api/generate",
                json=payload,
            )
            response.raise_for_status()
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail="Ollama no responde. Verifica que el servicio este iniciado y el modelo descargado.",
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                "Ollama tardo demasiado en responder. Si estas usando CPU, aumenta "
                "OLLAMA_TIMEOUT_SECONDS o baja OLLAMA_NUM_PREDICT."
            ),
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama devolvio un error: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con Ollama: {exc}") from exc

    data = response.json()
    raw_feedback = data.get("response", "").strip()
    if not raw_feedback:
        raise HTTPException(status_code=502, detail="Ollama respondio sin texto de feedback.")

    return sanitize_feedback(raw_feedback, class_metadata.get("blocked_topics", []))


def sanitize_feedback(text: str, blocked_topics: list[str]) -> str:
    return sanitize_blocked_topics(text, blocked_topics)


def _mode_instructions(mode: str) -> str:
    if mode == "practice":
        return """
- Sona docente, claro y alentador.
- Menciona primero lo que esta bien.
- Da pistas graduales para que el estudiante pueda revisar.
- No des la solucion completa.
- No avances sobre temas bloqueados.
""".strip()

    return """
- Usa una devolucion formal.
- Indica criterios cumplidos y pendientes.
- Justifica el resultado con el puntaje objetivo.
- No des pistas para resolver.
- No des la solucion completa.
""".strip()


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- Ninguno."
    return "\n".join(f"- {item}" for item in items)
