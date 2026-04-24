from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class FeedbackMode(str, Enum):
    practice = "practice"
    graded = "graded"


class SupportedLanguage(str, Enum):
    python = "python"
    html = "html"
    css = "css"
    js = "js"


class SubmittedFile(BaseModel):
    name: str = Field(..., min_length=1)
    content: str


class FeedbackRequest(BaseModel):
    class_id: str = Field(..., min_length=1)
    mode: FeedbackMode
    language: str = Field(..., min_length=1)
    files: List[SubmittedFile] = Field(..., min_length=1)


class FeedbackResponse(BaseModel):
    ok: bool
    passed: bool
    score: int
    errors: List[str]
    successes: List[str]
    context_used: List[str]
    feedback: str


class HealthResponse(BaseModel):
    ok: bool
