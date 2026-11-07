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


class Decision(str, Enum):
    """Overall gate decision on a tool call."""
    ALLOW = "ALLOW"
    WARN = "WARN"
    ASK = "ASK"
    BLOCK = "BLOCK"


class CheckTier(str, Enum):
    """
    Tier of authority for an individual verification check:
    - ORACLE_EXACT: Outcome decided by an authoritative contract; a failure is definitely wrong.
    - COERCIBLE: Implementation-strict type mismatch (e.g. numeric string, enum casing) that
      might be coerced by the downstream tool implementation. Never blocks.
    - COVERAGE_BOUNDED: Compared against an imperfect reference; failure means unsupported, not wrong.
    - UNCHECKABLE: Value cannot be checked against reference or contract (e.g. booleans, nulls).
    """
    ORACLE_EXACT = "ORACLE_EXACT"
    COERCIBLE = "COERCIBLE"
    COVERAGE_BOUNDED = "COVERAGE_BOUNDED"
    UNCHECKABLE = "UNCHECKABLE"


class OraclePolicy(str, Enum):
    """
    Policy for oracle/schema verification tiering (Prompt 5D):
    - COERCIBLE (default): Distinguishes genuine contract violations (ORACLE_EXACT)
      from coercible type mismatches (COERCIBLE).
    - LEGACY_STRICT: Legacy behavior where all schema mismatches fail under ORACLE_EXACT.
    """
    COERCIBLE = "coercible"
    LEGACY_STRICT = "legacy_strict"



class CheckOutcome(str, Enum):
    """Outcome of an individual verification check."""
    PASS = "PASS"
    FAIL = "FAIL"
    ABSTAIN = "ABSTAIN"


class CheckResult(BaseModel):
    """Structured result of an individual verification check."""
    check_id: str = Field(..., description="Unique check identifier (e.g. schema_type, arg_ground_number)")
    tier: CheckTier = Field(..., description="Authoritative tier of this check")
    outcome: CheckOutcome = Field(..., description="PASS, FAIL, or ABSTAIN")
    evidence_tier: Optional[str] = Field(default=None, description="Evidence rung (E1..E5)")
    arg_path: Optional[str] = Field(default=None, description="Argument name or path checked")
    reason: str = Field(default="", description="Human-readable explanation of outcome")
    details: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary check-specific metadata")


class ClarificationRequest(BaseModel):
    """Structured clarification request returned when decision is ASK."""
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments requiring clarification")
    values: Dict[str, Any] = Field(default_factory=dict, description="Proposed argument values")
    unsupported_reasons: List[str] = Field(default_factory=list, description="Why each argument value is unsupported")
    missing_evidence_tier: Optional[str] = Field(default="E1", description="Evidence tier that was missing")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional context or suggested valid schema options")


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
    decision: Optional[Decision] = Field(default=None, description="ALLOW, WARN, ASK, BLOCK")
    check_results: List[CheckResult] = Field(default_factory=list, description="Structured check results")


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
    decision: Optional[Decision] = Field(default=None, description="ALLOW, WARN, ASK, BLOCK")
    check_results: List[CheckResult] = Field(default_factory=list, description="Structured check results")


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
    decision: Optional[Decision] = Field(default=None, description="ALLOW, WARN, ASK, BLOCK")
    check_results: List[CheckResult] = Field(default_factory=list, description="Structured check results")
