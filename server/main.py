"""
Self-Reflective Hallucination Checker — FastMCP Server

Exposes:
  verify_logic_chain       — pre-execution structural verification of LLM reasoning chains
  verify_schema_alignment  — schema-drift verification for tool-call arguments

Session cleanup:
  A background Timer fires every SESSION_CLEANUP_INTERVAL_S seconds and
  evicts sessions that have not been accessed within SESSION_TTL_SECONDS
  (both defined in session/tracker.py).  This prevents unbounded memory
  growth in long-lived MCP server processes serving many agent sessions.
"""
import asyncio
import threading

from fastmcp import FastMCP

from server.models.schemas import (
    VerifyRequest, VerifyResponse,
    SchemaAlignmentRequest, SchemaAlignmentResponse,
    ArgumentGroundingRequest, ArgumentGroundingResponse,
)
from server.tools.verify_logic import run_verification
from server.tools.verify_grounded import run_grounded_verification
from server.tools.verify_arguments import run_argument_grounding
from server.tools.schema import run_schema_alignment
from server import session as session_module
from server.session.tracker import SESSION_TTL_SECONDS

# How often (seconds) to scan for and evict expired sessions.
SESSION_CLEANUP_INTERVAL_S = 300  # every 5 minutes


def _schedule_session_cleanup() -> None:
    """
    Periodically evict sessions that have not been accessed within TTL.
    Runs in a daemon thread so it does not block server shutdown.
    """
    removed = session_module.tracker.clear_expired(ttl=SESSION_TTL_SECONDS)
    if removed:
        # Log to stderr so it shows in MCP server output without importing logging
        import sys
        print(f"[session-cleanup] Evicted {removed} expired session(s).", file=sys.stderr)
    timer = threading.Timer(SESSION_CLEANUP_INTERVAL_S, _schedule_session_cleanup)
    timer.daemon = True
    timer.start()


mcp = FastMCP(
    name="hallucination-checker",
    instructions=(
        "ACTIVATION CRITERIA: Invoke `verify_logic_chain` during multi-step planning phases, "
        "before finalising tool call parameters extracted from retrieved context, or whenever "
        "the reasoning chain involves specific named entities, numeric values, or temporal claims. "
        "Invoke `verify_schema_alignment` before any tool call to check your argument structure "
        "against the current tool schema, especially in evolving tool ecosystems. "
        "OPERATIONAL INSTRUCTIONS: Pass the full proposed reasoning chain as `hypothesis` and "
        "the complete retrieved source context as `premise`. Act on the returned `feedback` before "
        "executing any downstream tool call flagged as inconsistent."
    ),
)


@mcp.tool(
    description=(
        "Verify whether a proposed reasoning chain or set of tool-call parameters is "
        "factually consistent with a provided source context. Uses SRL decomposition, "
        "semantic graph construction, and Graph Edit Distance alignment to detect "
        "hallucinated spans before execution. Detects: numeric mutations ($50→$500), "
        "entity substitutions, negation mismatches (did NOT transfer vs transferred), "
        "role swaps (Alice paid Bob vs Bob paid Alice), and temporal hallucinations. "
        "Returns a FactualConsistencyScore (0\u20131), a boolean consistency flag, a typed list "
        "of mismatched spans, corrective feedback, an optional constraint score (when "
        "user_query is provided), and an optional session drift alert (when session_id "
        "is provided)."
    )
)
async def verify_logic_chain(request: VerifyRequest) -> VerifyResponse:
    if request.mode == "grounded":
        return await asyncio.to_thread(
            run_grounded_verification,
            hypothesis=request.hypothesis,
            premise=request.premise,
            session_id=request.session_id,
            user_query=request.user_query,
        )
    return await asyncio.to_thread(
        run_verification,
        hypothesis=request.hypothesis,
        premise=request.premise,
        threshold=request.threshold,
        session_id=request.session_id,
        user_query=request.user_query,
    )


@mcp.tool(
    description=(
        "Verify that an agent's planned tool-call arguments match the current tool schema. "
        "Detects schema-drift errors (missing required fields) and format errors (type "
        "mismatches, enum violations, pattern failures, out-of-range numeric values) before "
        "execution. Returns a schema_drift_score (0\u20131), a boolean alignment flag, a typed "
        "mismatch list, and an optional session drift alert. Use this before every tool call "
        "in evolving tool ecosystems where schemas may have mutated."
    )
)
async def verify_schema_alignment(request: SchemaAlignmentRequest) -> SchemaAlignmentResponse:
    return await asyncio.to_thread(
        run_schema_alignment,
        agent_args=request.agent_args,
        tool_schema=request.tool_schema,
        session_id=request.session_id,
        threshold=request.threshold,
    )


@mcp.tool(
    description=(
        "Verify that each argument value of a planned tool call is supported by the conversation or source text it "
        "should come from. Type-aware and deterministic: numbers (including spelled-out), ISO dates and times against "
        "written dates and clock times, currency codes against currency names, and normalised/fuzzy string matching. "
        "Returns a call-level grounding score, per-argument verdicts, and the offending arguments. "
        "Limitation: no world knowledge (a ticker symbol for a company name is reported as ungrounded)."
    )
)
async def verify_argument_grounding(request: ArgumentGroundingRequest) -> ArgumentGroundingResponse:
    return await asyncio.to_thread(run_argument_grounding, request)


if __name__ == "__main__":
    # Start the background session-cleanup timer before serving
    _schedule_session_cleanup()
    mcp.run()
