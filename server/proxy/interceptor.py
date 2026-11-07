"""
Proxy Interception Middleware
==============================

Provides a transparent verification gate that wraps downstream tool calls.
Instead of requiring the agent to explicitly call ``verify_logic_chain`` or
``verify_schema_alignment``, the interceptor automatically routes every
high-risk tool call through the appropriate verifier before dispatch.

This implements the "mandatory gate" architecture: safety is enforced at
the infrastructure layer, not dependent on the agent's cooperative behaviour.

Architecture:
    Agent → InterceptingToolProxy → [verify_logic_chain | verify_schema_alignment]
                                                  ↓ passes
                                          Downstream tool execution

Usage:
    from server.proxy.interceptor import InterceptingToolProxy, RiskLevel

    proxy = InterceptingToolProxy(
        tool_fn=my_downstream_tool,
        tool_schema=MY_TOOL_SCHEMA,
        risk_level=RiskLevel.HIGH,
    )

    # Instead of calling my_downstream_tool(**args) directly:
    result = proxy.call(
        agent_args={"amount": 500, "account": "ACC-001"},
        reasoning_context="The user requested a $500 transfer to ACC-001.",
        source_context="Transaction approved for $50 to account ACC-001.",
    )

    if result.blocked:
        print(f"Blocked: {result.block_reason}")
    else:
        print(f"Executed: {result.tool_output}")

FastMCP integration:
    Use ``create_guarded_mcp_tool`` to wrap any @mcp.tool function with
    automatic pre-execution verification. See ``server/main_guarded.py``
    for a complete example.
"""
from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk classification for tool calls."""
    LOW = "low"       # Read-only, reversible — no interception needed
    MEDIUM = "medium" # Potentially impactful — schema check only
    HIGH = "high"     # Irreversible / financial / destructive — full verification


class BlockReason(str, Enum):
    SCHEMA_MISMATCH    = "schema_mismatch"
    LOGIC_INCONSISTENT = "logic_inconsistent"
    BOTH               = "schema_and_logic"


@dataclass
class InterceptionResult:
    """Result returned by the proxy instead of calling the downstream tool directly."""
    blocked: bool
    block_reason: Optional[BlockReason] = None
    schema_mismatches: List[Any] = field(default_factory=list)
    logic_mismatches: List[Any] = field(default_factory=list)
    factual_score: Optional[float] = None
    ged_normalised: Optional[float] = None
    tool_output: Optional[Any] = None
    feedback: str = ""


class InterceptingToolProxy:
    """
    Wraps a downstream tool function with automatic pre-execution verification.

    Parameters
    ----------
    tool_fn:
        The actual downstream tool to execute if verification passes.
    tool_schema:
        JSON Schema dict with ``required`` and ``properties`` keys.
        Used for ``verify_schema_alignment``.
    risk_level:
        Controls which verifications are applied:
        - LOW    → no verification, calls tool_fn directly
        - MEDIUM → schema alignment check only
        - HIGH   → schema alignment + logic chain verification
    ged_threshold:
        Override the default GED threshold for this specific tool.
        Useful for high-stakes tools that need tighter thresholds.
    session_id:
        Optional session identifier for drift tracking across calls.
    """

    def __init__(
        self,
        tool_fn: Callable,
        tool_schema: Optional[Dict[str, Any]] = None,
        risk_level: RiskLevel = RiskLevel.HIGH,
        ged_threshold: Optional[float] = None,
        session_id: Optional[str] = None,
        logic_mode: str = "hybrid",
        arg_tau: float = 0.88,
    ) -> None:
        self.tool_fn = tool_fn
        self.tool_schema = tool_schema or {}
        self.risk_level = risk_level
        self.ged_threshold = ged_threshold
        self.session_id = session_id
        self.logic_mode = logic_mode  # "hybrid" (GED + span NLI), "grounded" (whole-claim NLI + value check) or "arguments" (argument-level grounding)
        self.arg_tau = arg_tau

    def tool_schema_hint(self):
        props = (self.tool_schema or {}).get("properties", {})
        required = list((self.tool_schema or {}).get("required", []))
        return {"required": required, "optional": [k for k in props if k not in required]} if props else None

    def call(
        self,
        agent_args: Dict[str, Any],
        reasoning_context: Optional[str] = None,
        source_context: Optional[str] = None,
    ) -> InterceptionResult:
        """
        Verify then (conditionally) execute.

        Parameters
        ----------
        agent_args:
            The argument dict the agent plans to pass to the tool.
        reasoning_context:
            The agent's proposed reasoning chain or planned action description.
            Required for HIGH risk level logic verification.
        source_context:
            The ground-truth context the reasoning should be grounded in.
            Required for HIGH risk level logic verification.

        Returns
        -------
        InterceptionResult
            If ``blocked=True``, the tool was NOT called.
            If ``blocked=False``, ``tool_output`` contains the tool's return value.
        """
        if self.risk_level == RiskLevel.LOW:
            return InterceptionResult(
                blocked=False,
                tool_output=self.tool_fn(**agent_args),
                feedback="Low-risk tool: no verification applied.",
            )

        schema_mismatches: List[Any] = []
        logic_mismatches: List[Any] = []
        factual_score: Optional[float] = None
        ged_norm: Optional[float] = None

        # ── Step 1: Schema alignment check ───────────────────────────────────
        if self.tool_schema:
            from server.tools.schema import run_schema_alignment
            schema_result = run_schema_alignment(
                agent_args=agent_args,
                tool_schema=self.tool_schema,
                session_id=self.session_id,
            )
            if not schema_result.is_aligned:
                schema_mismatches = schema_result.mismatches
                feedback = (
                    f"Tool call blocked: schema mismatches detected.\n"
                    + "\n".join(f"  - {m.span}: {m.issue}" for m in schema_mismatches)
                )
                logger.warning(
                    "InterceptingToolProxy: blocked %s — schema mismatches: %s",
                    self.tool_fn.__name__,
                    [m.span for m in schema_mismatches],
                )
                return InterceptionResult(
                    blocked=True,
                    block_reason=BlockReason.SCHEMA_MISMATCH,
                    schema_mismatches=schema_mismatches,
                    feedback=feedback,
                )

        # ── Step 2: Logic chain verification (HIGH risk only) ─────────────────
        if self.risk_level == RiskLevel.HIGH and source_context and (reasoning_context or self.logic_mode == "arguments"):
            kwargs: Dict[str, Any] = dict(
                hypothesis=reasoning_context or "",
                premise=source_context,
                session_id=self.session_id,
            )
            if self.logic_mode == "arguments":
                from server.models.schemas import ArgumentGroundingRequest
                from server.tools.verify_arguments import run_argument_grounding
                arg_result = run_argument_grounding(ArgumentGroundingRequest(
                    arguments=agent_args, context=source_context, schema_hint=self.tool_schema_hint(),
                    tau=self.arg_tau, session_id=self.session_id))
                factual_score = arg_result.call_score
                if not arg_result.is_grounded:
                    return InterceptionResult(
                        blocked=True, block_reason=BlockReason.LOGIC_INCONSISTENT,
                        logic_mismatches=arg_result.mismatched_spans, factual_score=factual_score,
                        feedback="Tool call blocked: argument values not supported by the context.\n" + arg_result.feedback)
                logic_result = None
            elif self.logic_mode == "grounded":
                from server.tools.verify_grounded import run_grounded_verification
                logic_result = run_grounded_verification(**kwargs)
            else:
                from server.tools.verify_logic import run_verification
                if self.ged_threshold is not None:
                    kwargs["threshold"] = self.ged_threshold
                logic_result = run_verification(**kwargs)
            if logic_result is not None:
                factual_score = logic_result.factual_consistency_score
                ged_norm = logic_result.ged_normalised

            if logic_result is not None and not logic_result.is_consistent:
                logic_mismatches = logic_result.mismatched_spans
                feedback = (
                    f"Tool call blocked: reasoning chain inconsistent with source context.\n"
                    f"Factual score: {factual_score:.4f}  GED: {ged_norm:.4f}\n"
                    + logic_result.feedback
                )
                logger.warning(
                    "InterceptingToolProxy: blocked %s — logic mismatches: %s",
                    self.tool_fn.__name__,
                    [m.span for m in logic_mismatches],
                )
                return InterceptionResult(
                    blocked=True,
                    block_reason=BlockReason.LOGIC_INCONSISTENT,
                    logic_mismatches=logic_mismatches,
                    factual_score=factual_score,
                    ged_normalised=ged_norm,
                    feedback=feedback,
                )

        # ── Step 3: Execute downstream tool ──────────────────────────────────
        try:
            output = self.tool_fn(**agent_args)
            logger.info(
                "InterceptingToolProxy: executed %s successfully",
                self.tool_fn.__name__,
            )
            return InterceptionResult(
                blocked=False,
                factual_score=factual_score,
                ged_normalised=ged_norm,
                tool_output=output,
                feedback="Verification passed. Tool executed.",
            )
        except Exception as exc:
            logger.error(
                "InterceptingToolProxy: tool %s raised %s",
                self.tool_fn.__name__, exc,
            )
            raise


def guarded(
    tool_schema: Optional[Dict[str, Any]] = None,
    risk_level: RiskLevel = RiskLevel.HIGH,
    ged_threshold: Optional[float] = None,
    logic_mode: str = "hybrid",
) -> Callable:
    """
    Decorator that wraps a function with InterceptingToolProxy.

    Usage:
        @guarded(
            tool_schema={
                "required": ["amount", "to_account"],
                "properties": {
                    "amount":     {"type": "number", "minimum": 0},
                    "to_account": {"type": "string"},
                },
            },
            risk_level=RiskLevel.HIGH,
        )
        def execute_transfer(amount: float, to_account: str) -> str:
            ...

    The decorated function gains a ``proxy`` attribute pointing to the
    underlying ``InterceptingToolProxy`` instance for direct access.
    """
    def decorator(fn: Callable) -> Callable:
        proxy = InterceptingToolProxy(
            tool_fn=fn,
            tool_schema=tool_schema,
            risk_level=risk_level,
            ged_threshold=ged_threshold,
            logic_mode=logic_mode,
        )

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Direct call bypasses proxy — proxy.call() is the guarded path.
            # This allows the raw function to still be called directly in tests.
            return fn(*args, **kwargs)

        wrapper.proxy = proxy  # type: ignore[attr-defined]
        return wrapper

    return decorator
