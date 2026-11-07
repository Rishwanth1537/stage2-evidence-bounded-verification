"""Pydantic schemas for tool I/O."""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from server.config import GED_THRESHOLD


class HallucinationType(str, Enum):
    SCHEMA = "schema"
    FORMAT = "format"
    CONTENT = "content"


class MismatchedSpan(BaseModel):
    span: str
    issue: str
    hallucination_type: HallucinationType


class VerifyRequest(BaseModel):
    hypothesis: str = Field(..., description="The LLM's proposed reasoning chain or planned tool call parameters.")
    premise: str = Field(..., description="Ground-truth context or retrieved evidence the hypothesis should be grounded in.")
    threshold: float = Field(default=GED_THRESHOLD, ge=0.0, le=1.0, description="Normalised GED threshold above which the chain is flagged as inconsistent.")
    session_id: Optional[str] = Field(default=None, description="Optional session identifier for drift tracking.")
    user_query: Optional[str] = Field(default=None, description="Original user query for constraint extraction.")
    mode: Literal["hybrid", "grounded"] = Field(default="hybrid", description="'hybrid' = GED + span NLI (original); 'grounded' = whole-claim NLI plus a deterministic value check.")


class VerifyResponse(BaseModel):
    factual_consistency_score: float = Field(..., ge=0.0, le=1.0, description="1.0 = fully consistent, 0.0 = fully inconsistent.")
    is_consistent: bool
    mismatched_spans: List[MismatchedSpan]
    feedback: str
    ged_raw: float
    ged_normalised: float
    constraint_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    drift_alert: Optional[bool] = None
    session_mean_score: Optional[float] = None
    degraded: bool = Field(default=False, description="True if any verification step ran in degraded mode.")
    degraded_reasons: List[str] = Field(default_factory=list, description="Reasons for degradation.")


class SchemaAlignmentRequest(BaseModel):
    agent_args: Dict[str, Any] = Field(..., description="The agent-provided argument dict.")
    tool_schema: Dict[str, Any] = Field(..., description="JSON Schema object with 'properties' and 'required' keys.")
    session_id: Optional[str] = None
    threshold: float = Field(default=GED_THRESHOLD, ge=0.0, le=1.0)


class SchemaAlignmentResponse(BaseModel):
    is_aligned: bool
    schema_drift_score: float = Field(..., ge=0.0, le=1.0)
    mismatches: List[MismatchedSpan]
    drift_alert: Optional[bool] = None
    session_mean_score: Optional[float] = None
    degraded: bool = Field(default=False, description="True if any verification step ran in degraded mode.")
    degraded_reasons: List[str] = Field(default_factory=list, description="Reasons for degradation.")


class ArgumentGroundingRequest(BaseModel):
    arguments: Dict[str, Any] = Field(..., description="The planned tool-call arguments.")
    context: str = Field(..., description="The conversation or source text the argument values should be grounded in.")
    schema_hint: Optional[Dict[str, Any]] = Field(default=None, description="Optional {'required': [...], 'optional': [...]}; used only with policy='required_only'.")
    tau: float = Field(default=0.88, ge=0.0, le=1.0, description="Block iff the call-level grounding score is below tau (calibrate with conformal_threshold for a false-block budget).")
    policy: Literal["strict", "required_only"] = Field(default="strict")
    session_id: Optional[str] = None


class ArgumentVerdictModel(BaseModel):
    argument: str
    value: Any
    verdict: str
    score: float
    reason: str = ""


class ArgumentGroundingResponse(BaseModel):
    is_grounded: bool
    call_score: float = Field(..., ge=0.0, le=1.0)
    tau: float
    per_argument: List[ArgumentVerdictModel]
    mismatched_spans: List[MismatchedSpan]
    feedback: str
    degraded: bool = Field(default=False, description="True if any verification step ran in degraded mode.")
    degraded_reasons: List[str] = Field(default_factory=list, description="Reasons for degradation.")
