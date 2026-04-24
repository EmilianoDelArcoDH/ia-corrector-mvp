from fastapi import FastAPI, HTTPException

from app.grader import grade_submission
from app.llm import generate_feedback
from app.rag import get_class_metadata, search_chunks
from app.schemas import FeedbackRequest, FeedbackResponse, HealthResponse
from app.utils import combined_file_content


app = FastAPI(
    title="ia-corrector-mvp",
    description="API para corrección educativa con grader objetivo y feedback generado por Ollama.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(payload: FeedbackRequest) -> FeedbackResponse:
    class_metadata = get_class_metadata(payload.class_id, payload.language)
    if class_metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró metadata para class_id={payload.class_id} y language={payload.language}.",
        )

    grader_result = grade_submission(payload.language, payload.files)
    query = " ".join(
        [
            combined_file_content(payload.files),
            " ".join(grader_result["errors"]),
            " ".join(grader_result["successes"]),
            " ".join(class_metadata.get("learning_objectives", [])),
        ]
    )
    context_chunks = search_chunks(
        class_id=payload.class_id,
        language=payload.language,
        query=query,
        top_k=4,
    )

    feedback_text = await generate_feedback(
        mode=payload.mode.value,
        language=payload.language,
        class_metadata=class_metadata,
        grader_result=grader_result,
        context_chunks=context_chunks,
    )

    return FeedbackResponse(
        ok=True,
        passed=grader_result["passed"],
        score=grader_result["score"],
        errors=grader_result["errors"],
        successes=grader_result["successes"],
        context_used=[chunk["id"] for chunk in context_chunks],
        feedback=feedback_text,
    )
