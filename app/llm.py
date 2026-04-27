import os
from typing import Any

import httpx

from app.utils import sanitize_blocked_topics


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "220"))
OLLAMA_CONTEXT_CHARS = int(os.getenv("OLLAMA_CONTEXT_CHARS", "900"))


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
    context = "\n".join(
        f"- {chunk.get('title')}: {_truncate_text(str(chunk.get('content', '')), OLLAMA_CONTEXT_CHARS)}"
        for chunk in context_chunks
    )
    if not context:
        context = "- No se recupero contexto especifico."

    return f"""
Sos un asistente pedagogico de Digital House para revisar actividades educativas.

Reglas obligatorias:
- Primero respeta el resultado del corrector objetivo. No inventes errores ni aciertos.
- Usa solo la lista de errores objetivos como criterios pendientes. No transformes objetivos generales de la clase en pendientes.
- No sugieras formulas, funciones, graficos, indicadores o mejoras que la actividad entregada no pida explicitamente.
- Si la lista de errores objetivos esta vacia, no menciones pendientes, criterios pendientes ni pistas de mejora obligatorias.
- No recomiendes agregar algo que ya figura en la lista de aciertos.
- Si en los aciertos aparecen formulas detectadas o valores calculados, explicalos en lenguaje simple: "esta perfecto usar X porque nos ayuda a Y".
- No nombres formulas que no aparezcan en los aciertos objetivos.
- No des una solucion completa ni codigo completo.
- No uses ni recomiendes estos temas bloqueados: {", ".join(blocked_topics)}.
- Si un tema bloqueado parece util, omitilo y reformula con los temas permitidos.
- Redacta en espanol claro, con tono cercano, colaborativo y entusiasta.
- Evita sonar autoritario, distante o punitivo. Acompana el aprendizaje con seguridad y calidez.
- Usa oraciones concisas, voz activa y ejemplos conectados con la actividad.

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

Importante: el contexto recuperado es material de apoyo, no una lista de requisitos. Los requisitos evaluados son solo los del resultado objetivo.

Escribi una devolucion breve y util.
Estructura:
1. Un parrafo corto de lectura general, con tono de acompanamiento.
2. "Lo logrado" solo con aciertos objetivos.
3. Si hay formulas detectadas, agrega una frase breve explicando para que ayuda cada una.
4. "Para seguir trabajando" solo si hay errores objetivos. Si no hay errores, escribi "No se detectaron pendientes objetivos en esta revision."
5. Si Aprobado es False, cerra indicando que debe reelaborar la actividad y volver a entregarla.
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
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError, httpx.HTTPError):
        return fallback_feedback(
            mode=mode,
            grader_result=grader_result,
            class_metadata=class_metadata,
        )

    data = response.json()
    raw_feedback = data.get("response", "").strip()
    if not raw_feedback:
        return fallback_feedback(
            mode=mode,
            grader_result=grader_result,
            class_metadata=class_metadata,
        )

    if not grader_result.get("errors") and _mentions_pending_work(raw_feedback):
        raw_feedback = successful_feedback(grader_result=grader_result, class_metadata=class_metadata)

    return sanitize_feedback(raw_feedback, class_metadata.get("blocked_topics", []))


def sanitize_feedback(text: str, blocked_topics: list[str]) -> str:
    return sanitize_blocked_topics(text, blocked_topics)


def fallback_feedback(*, mode: str, grader_result: dict[str, Any], class_metadata: dict[str, Any]) -> str:
    score = grader_result.get("score")
    successes = grader_result.get("successes", [])
    errors = grader_result.get("errors", [])
    class_title = class_metadata.get("title", "la clase")

    intro = f"Revisamos la entrega de {class_title} y el resultado fue {score}/100."
    if mode == "graded":
        intro = f"Revisamos la entrega de {class_title} con los criterios de la actividad: puntaje {score}/100."

    parts = [intro]
    if successes:
        parts.append("Logrado: " + " ".join(successes[:3]))
    if errors:
        parts.append("Para seguir trabajando: " + " ".join(errors[:3]))
        parts.append("Reelabora la actividad tomando estas observaciones y volve a entregarla para una nueva revision.")
    else:
        parts.append("No se detectaron pendientes principales con las reglas automaticas.")

    parts.append(
        "Nota: el modelo local de feedback no respondio a tiempo, asi que esta devolucion se genero con el corrector objetivo."
    )
    return sanitize_feedback("\n\n".join(parts), class_metadata.get("blocked_topics", []))


def successful_feedback(*, grader_result: dict[str, Any], class_metadata: dict[str, Any]) -> str:
    score = grader_result.get("score")
    successes = grader_result.get("successes", [])
    class_title = class_metadata.get("title", "la clase")

    parts = [
        f"Muy buen trabajo: la entrega cumple con los criterios revisados para {class_title} y obtuvo {score}/100.",
    ]
    if successes:
        parts.append("Lo logrado: " + " ".join(successes[:5]))
    parts.append("No se detectaron pendientes objetivos en esta revision.")
    return "\n\n".join(parts)


def _mentions_pending_work(text: str) -> bool:
    lowered = text.lower()
    pending_markers = [
        "lo pendiente",
        "criterios pendientes",
        "pendiente:",
        "areas para mejorar",
        "áreas para mejorar",
        "debes mejorar",
        "para mejorar",
        "considera agregar",
        "asegurate de",
        "asegúrate de",
        "revisa la",
        "revisa si",
    ]
    return any(marker in lowered for marker in pending_markers)


def _truncate_text(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rsplit(" ", 1)[0] + "..."


def _mode_instructions(mode: str) -> str:
    if mode == "practice":
        return """
- Sona docente, claro, cercano y alentador.
- Menciona primero lo que esta bien.
- Da pistas graduales solo para errores objetivos detectados.
- No des la solucion completa.
- No avances sobre temas bloqueados.
""".strip()

    return """
- Usa una devolucion clara y confiable.
- Indica criterios cumplidos y solo los pendientes detectados por el corrector objetivo.
- Justifica el resultado con el puntaje objetivo.
- No des pistas para resolver.
- No des la solucion completa.
""".strip()


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- Ninguno."
    return "\n".join(f"- {item}" for item in items)
