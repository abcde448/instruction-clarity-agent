"""Shared Pydantic models for structured JSON I/O."""

from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field


class ClarityStatus(str, Enum):
    CLEAR = "clear"
    UNCLEAR = "unclear"


class ClarityResult(BaseModel):
    status: ClarityStatus
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    reason: str


class ActionExtractionResult(BaseModel):
    actions: list[str]
    deadline: Optional[str] = None
    priority: Optional[str] = None


class ClarificationResult(BaseModel):
    instruction: str
    questions: list[str]


class AgentResponse(BaseModel):
    instruction: str
    clarity: ClarityResult
    result: Union[ActionExtractionResult, ClarificationResult]
