"""
Guarded FastMCP Server — Proxy Interception Example
=====================================================

Demonstrates the "mandatory gate" architecture where downstream tool calls
are automatically intercepted and verified BEFORE execution, without
requiring the agent to explicitly call verify_logic_chain.

This is an EXAMPLE server showing the pattern. In production you would
replace the stub downstream functions with your real tool implementations.

Usage:
    python server/main_guarded.py

Configure in any MCP client:
    {
      "mcpServers": {
        "guarded-agent": {
          "command": "python",
          "args": ["server/main_guarded.py"]
        }
      }
    }

Pattern:
    ┌─────────────────────────────────────────────────────────┐
    │  Agent calls execute_financial_transfer(amount=500, …)  │
    │                         ↓                               │
    │     InterceptingToolProxy.call(agent_args, context)     │
    │           ↓                          ↓                  │
    │   verify_schema_alignment   verify_logic_chain          │
    │     (synchronous JSON             (GED + NLI)           │
    │      Schema check)                                      │
    │           ↓ passes               ↓ passes               │
    │           └──────────┬───────────┘                      │
    │                      ↓                                  │
    │           Downstream tool executes                      │
    │                      ↓                                  │
    │               Result returned                           │
    └─────────────────────────────────────────────────────────┘
"""
import asyncio
from typing import Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from server.proxy.interceptor import InterceptingToolProxy, RiskLevel, InterceptionResult

mcp = FastMCP(
    name="guarded-agent",
    instructions=(
        "This server provides tools that are automatically verified before execution. "
        "For high-risk tools, pass 'reasoning' (your planned action description) and "
        "'context' (the source document or retrieved evidence) to enable full "
        "pre-execution logic verification. If the tool call is blocked, revise your "
        "reasoning based on the returned feedback before retrying."
    ),
)


# ── Example downstream tool implementations ──────────────────────────────────

def _downstream_financial_transfer(
    from_account: str,
    to_account: str,
    amount: float,
    currency: str,
) -> str:
    """Stub: replace with real financial transfer implementation."""
    return f"Transferred {currency} {amount:.2f} from {from_account} to {to_account}."


def _downstream_deploy_service(
    service_name: str,
    version: str,
    environment: str,
    approved_by: str,
) -> str:
    """Stub: replace with real deployment implementation."""
    return f"Deployed {service_name}:{version} to {environment} (approved by {approved_by})."


def _downstream_delete_records(
    table: str,
    filter_expression: str,
    confirmed: bool,
) -> str:
    """Stub: replace with real database delete implementation."""
    return f"Deleted records from {table} where {filter_expression}."


# ── Intercepting proxies with tool-specific schemas ───────────────────────────

_TRANSFER_PROXY = InterceptingToolProxy(
    tool_fn=_downstream_financial_transfer,
    tool_schema={
        "required": ["from_account", "to_account", "amount", "currency"],
        "properties": {
            "from_account": {"type": "string"},
            "to_account":   {"type": "string"},
            "amount":       {"type": "number", "minimum": 0},
            "currency":     {"type": "string", "enum": ["USD", "EUR", "GBP", "JPY"]},
        },
    },
    risk_level=RiskLevel.HIGH,
    ged_threshold=0.30,  # Tighter threshold for financial operations
)

_DEPLOY_PROXY = InterceptingToolProxy(
    tool_fn=_downstream_deploy_service,
    tool_schema={
        "required": ["service_name", "version", "environment", "approved_by"],
        "properties": {
            "service_name": {"type": "string"},
            "version":      {"type": "string"},
            "environment":  {"type": "string", "enum": ["staging", "production"]},
            "approved_by":  {"type": "string"},
        },
    },
    risk_level=RiskLevel.HIGH,
    ged_threshold=0.25,  # Very tight for production deployments
)

_DELETE_PROXY = InterceptingToolProxy(
    tool_fn=_downstream_delete_records,
    tool_schema={
        "required": ["table", "filter_expression", "confirmed"],
        "properties": {
            "table":             {"type": "string"},
            "filter_expression": {"type": "string", "minLength": 3},
            "confirmed":         {"type": "boolean"},
        },
    },
    risk_level=RiskLevel.HIGH,
    ged_threshold=0.20,  # Strictest threshold for destructive operations
)


# ── MCP tool request/response schemas ────────────────────────────────────────

class GuardedTransferRequest(BaseModel):
    from_account: str = Field(..., description="Source account identifier.")
    to_account:   str = Field(..., description="Destination account identifier.")
    amount:       float = Field(..., description="Transfer amount (positive number).")
    currency:     str = Field(..., description="Currency code: USD, EUR, GBP, or JPY.")
    reasoning:    Optional[str] = Field(None, description="Agent's planned action description for logic verification.")
    context:      Optional[str] = Field(None, description="Source document or evidence the reasoning is grounded in.")


class GuardedDeployRequest(BaseModel):
    service_name: str = Field(..., description="Name of the service to deploy.")
    version:      str = Field(..., description="Version tag to deploy (e.g. v2.4.0).")
    environment:  str = Field(..., description="Target environment: staging or production.")
    approved_by:  str = Field(..., description="Approver's identifier.")
    reasoning:    Optional[str] = Field(None, description="Agent's planned action description.")
    context:      Optional[str] = Field(None, description="Source runbook or approval document.")


class GuardedDeleteRequest(BaseModel):
    table:             str  = Field(..., description="Database table to delete from.")
    filter_expression: str  = Field(..., description="WHERE clause filter (must be specific).")
    confirmed:         bool = Field(..., description="Explicit confirmation flag.")
    reasoning:         Optional[str] = Field(None, description="Agent's planned action description.")
    context:           Optional[str] = Field(None, description="Source document justifying the deletion.")


class GuardedToolResponse(BaseModel):
    success:      bool
    blocked:      bool
    block_reason: Optional[str] = None
    feedback:     str
    result:       Optional[str] = None
    factual_score: Optional[float] = None


# ── MCP tool definitions ─────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Execute a financial transfer with automatic pre-execution verification. "
        "Schema and logic are verified before any funds move. "
        "Provide 'reasoning' and 'context' for full logic chain verification — "
        "without them only schema validation is applied."
    )
)
async def execute_financial_transfer(request: GuardedTransferRequest) -> GuardedToolResponse:
    agent_args = {
        "from_account": request.from_account,
        "to_account":   request.to_account,
        "amount":       request.amount,
        "currency":     request.currency,
    }
    result: InterceptionResult = await asyncio.to_thread(
        _TRANSFER_PROXY.call,
        agent_args=agent_args,
        reasoning_context=request.reasoning,
        source_context=request.context,
    )
    return GuardedToolResponse(
        success=not result.blocked,
        blocked=result.blocked,
        block_reason=result.block_reason.value if result.block_reason else None,
        feedback=result.feedback,
        result=str(result.tool_output) if result.tool_output else None,
        factual_score=result.factual_score,
    )


@mcp.tool(
    description=(
        "Deploy a service version with automatic pre-execution verification. "
        "Version strings, environment names, and approval fields are validated. "
        "Provide 'reasoning' and 'context' (the deployment runbook) for full "
        "version-hallucination detection."
    )
)
async def execute_service_deploy(request: GuardedDeployRequest) -> GuardedToolResponse:
    agent_args = {
        "service_name": request.service_name,
        "version":      request.version,
        "environment":  request.environment,
        "approved_by":  request.approved_by,
    }
    result: InterceptionResult = await asyncio.to_thread(
        _DEPLOY_PROXY.call,
        agent_args=agent_args,
        reasoning_context=request.reasoning,
        source_context=request.context,
    )
    return GuardedToolResponse(
        success=not result.blocked,
        blocked=result.blocked,
        block_reason=result.block_reason.value if result.block_reason else None,
        feedback=result.feedback,
        result=str(result.tool_output) if result.tool_output else None,
        factual_score=result.factual_score,
    )


@mcp.tool(
    description=(
        "Delete database records with automatic pre-execution verification. "
        "The filter expression must be specific (minLength 3). Confirmed=true is required. "
        "Provide 'reasoning' and 'context' for full logic verification before any "
        "destructive operation is executed."
    )
)
async def execute_database_delete(request: GuardedDeleteRequest) -> GuardedToolResponse:
    agent_args = {
        "table":             request.table,
        "filter_expression": request.filter_expression,
        "confirmed":         request.confirmed,
    }
    result: InterceptionResult = await asyncio.to_thread(
        _DELETE_PROXY.call,
        agent_args=agent_args,
        reasoning_context=request.reasoning,
        source_context=request.context,
    )
    return GuardedToolResponse(
        success=not result.blocked,
        blocked=result.blocked,
        block_reason=result.block_reason.value if result.block_reason else None,
        feedback=result.feedback,
        result=str(result.tool_output) if result.tool_output else None,
        factual_score=result.factual_score,
    )


if __name__ == "__main__":
    mcp.run()
