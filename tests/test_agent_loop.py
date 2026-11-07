"""
End-to-end agent loop integration tests.

These tests simulate a realistic agentic workflow where an LLM agent:
  1. Retrieves context (source document / tool schema)
  2. Forms a reasoning chain or tool-call plan
  3. Calls verify_logic_chain / verify_schema_alignment BEFORE executing
  4. Respects the verdict — only executes if is_consistent / is_aligned is True

This validates the primary use-case of the hallucination checker as a
pre-execution gate, NOT just an offline evaluator.

Run with real models:
    pytest tests/test_agent_loop.py -m integration -v

Skipped automatically if ML models are not installed.
"""
from __future__ import annotations
import pytest
from typing import Dict, Any, Optional, List

spacy       = pytest.importorskip("spacy",        reason="spaCy not installed")
transformers = pytest.importorskip("transformers", reason="transformers not installed")

from server.tools.verify_logic import run_verification
from server.tools.schema import run_schema_alignment
from server.models.schemas import HallucinationType

pytestmark = pytest.mark.integration


# ── Simulated downstream tool registry ────────────────────────────────────────

_EXECUTION_LOG: List[str] = []


def _execute_transfer(from_acc: str, to_acc: str, amount: float) -> str:
    """Simulated irreversible financial transfer tool."""
    entry = f"TRANSFER {amount} from {from_acc} to {to_acc}"
    _EXECUTION_LOG.append(entry)
    return entry


def _execute_deploy(service: str, version: str, environment: str) -> str:
    """Simulated deployment tool."""
    entry = f"DEPLOY {service}:{version} → {environment}"
    _EXECUTION_LOG.append(entry)
    return entry


def _execute_delete(path: str) -> str:
    """Simulated file deletion tool."""
    entry = f"DELETE {path}"
    _EXECUTION_LOG.append(entry)
    return entry


def _agent_transfer_with_gate(
    hypothesis: str,
    context: str,
    from_acc: str,
    to_acc: str,
    amount: float,
) -> Dict[str, Any]:
    """
    Simulated agent that:
    1. Verifies its reasoning chain against source context
    2. Only executes the transfer if the checker approves
    Returns the verification result and whether execution happened.
    """
    result = run_verification(hypothesis=hypothesis, premise=context)
    executed = False
    if result.is_consistent:
        _execute_transfer(from_acc, to_acc, amount)
        executed = True
    return {"verified": result, "executed": executed}


def _agent_deploy_with_schema_gate(
    agent_args: Dict[str, Any],
    tool_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Simulated agent that validates its tool-call arguments before deploying.
    """
    result = run_schema_alignment(agent_args=agent_args, tool_schema=tool_schema)
    executed = False
    if result.is_aligned:
        _execute_deploy(
            service=agent_args.get("service", "?"),
            version=agent_args.get("version", "?"),
            environment=agent_args.get("environment", "?"),
        )
        executed = True
    return {"verified": result, "executed": executed}


# ── Test cases ─────────────────────────────────────────────────────────────────

class TestNumericHallucinationBlocked:
    """Agent hallucinates a transfer amount — checker must block execution."""

    def test_hallucinated_amount_blocks_transfer(self):
        """
        Source context: Alice sent $50 to Bob.
        Agent reasoning (hallucinated): Alice transferred $500 to Bob.
        Expected: checker blocks the transfer.
        """
        _EXECUTION_LOG.clear()
        context = "The transaction log shows Alice transferred $50 to Bob on Monday."
        hallucinated_hypothesis = "Alice transferred $500 to Bob on Monday."

        outcome = _agent_transfer_with_gate(
            hypothesis=hallucinated_hypothesis,
            context=context,
            from_acc="Alice",
            to_acc="Bob",
            amount=500.0,
        )

        assert outcome["executed"] is False, (
            f"Transfer should have been blocked. "
            f"GED={outcome['verified'].ged_normalised:.4f}, "
            f"score={outcome['verified'].factual_consistency_score:.4f}, "
            f"mismatches={outcome['verified'].mismatched_spans}"
        )
        assert len(_EXECUTION_LOG) == 0, "No transfer should appear in execution log"

    def test_correct_amount_allows_transfer(self):
        """
        Source context: Alice sent $50 to Bob.
        Agent reasoning (correct): Alice transferred $50 to Bob.
        Expected: checker passes and transfer executes.
        """
        _EXECUTION_LOG.clear()
        context = "The transaction log shows Alice transferred $50 to Bob on Monday."
        correct_hypothesis = "Alice transferred $50 to Bob."

        outcome = _agent_transfer_with_gate(
            hypothesis=correct_hypothesis,
            context=context,
            from_acc="Alice",
            to_acc="Bob",
            amount=50.0,
        )

        assert outcome["executed"] is True, (
            f"Transfer should have been allowed. "
            f"GED={outcome['verified'].ged_normalised:.4f}, "
            f"score={outcome['verified'].factual_consistency_score:.4f}"
        )
        assert len(_EXECUTION_LOG) == 1


class TestVersionHallucinationBlocked:
    """Agent hallucinates a version string — deployment must be blocked."""

    def test_wrong_version_blocks_deploy(self):
        """
        Source context: deploy v2.4.0.
        Agent plan (hallucinated): deploy v2.4.1.
        Expected: blocks deployment.
        """
        _EXECUTION_LOG.clear()
        context = "Deployment runbook: deploy service 'api' version v2.4.0 to production."
        hallucinated = "I will deploy service api version 2.4.1 to production."

        result = run_verification(hypothesis=hallucinated, premise=context)
        if result.is_consistent:
            _execute_deploy("api", "2.4.1", "production")

        assert result.is_consistent is False, (
            f"Version hallucination 2.4.0→2.4.1 must be blocked. "
            f"GED={result.ged_normalised:.4f}, score={result.factual_consistency_score:.4f}"
        )
        assert len(_EXECUTION_LOG) == 0

    def test_correct_version_allows_deploy(self):
        """
        Source context: deploy v2.4.0.
        Agent plan (correct): deploy v2.4.0.
        Expected: deployment proceeds.
        """
        _EXECUTION_LOG.clear()
        context = "Deployment runbook: deploy service 'api' version v2.4.0 to production."
        correct = "I will deploy service api version 2.4.0 to production."

        result = run_verification(hypothesis=correct, premise=context)
        if result.is_consistent:
            _execute_deploy("api", "2.4.0", "production")

        assert result.is_consistent is True, (
            f"Correct version should pass. "
            f"GED={result.ged_normalised:.4f}, score={result.factual_consistency_score:.4f}"
        )
        assert len(_EXECUTION_LOG) == 1


class TestNegationHallucinationBlocked:
    """Agent drops a negation from a constraint — must be caught."""

    def test_negation_drop_blocks_action(self):
        """
        Context: do NOT write to production database.
        Agent plan: write to production database.
        Expected: blocks the write.
        """
        context = "The maintenance runbook states: do NOT write to the production database during the freeze window."
        hallucinated = "The agent will write to the production database."

        result = run_verification(hypothesis=hallucinated, premise=context)

        assert result.is_consistent is False, (
            f"Negation drop must be caught. "
            f"GED={result.ged_normalised:.4f}, mismatches={result.mismatched_spans}"
        )

    def test_consistent_negation_passes(self):
        """
        Context: do NOT write to production database.
        Agent plan: do not write to production database.
        Expected: passes.
        """
        context = "The maintenance runbook states: do NOT write to the production database during the freeze window."
        correct = "The agent will not write to the production database during the freeze window."

        result = run_verification(hypothesis=correct, premise=context)
        assert result.is_consistent is True, (
            f"Consistent negation should pass. GED={result.ged_normalised:.4f}"
        )


class TestSchemaGateBlocking:
    """Schema alignment gate blocks malformed tool calls before execution."""

    _DEPLOY_SCHEMA = {
        "required": ["service_name", "version", "environment", "approved_by"],
        "properties": {
            "service_name": {"type": "string"},
            "version":      {"type": "string"},
            "environment":  {"type": "string", "enum": ["staging", "production"]},
            "approved_by":  {"type": "string"},
        },
    }

    def test_missing_approval_blocks_deploy(self):
        """
        Agent forgets required 'approved_by' field — deployment must be blocked.
        """
        _EXECUTION_LOG.clear()
        agent_args = {
            "service_name": "payment-service",
            "version": "v3.1.0",
            "environment": "production",
            # approved_by missing
        }
        outcome = _agent_deploy_with_schema_gate(agent_args, self._DEPLOY_SCHEMA)

        assert outcome["executed"] is False, "Missing 'approved_by' must block deployment"
        schema_mismatches = [
            m for m in outcome["verified"].mismatches
            if m.hallucination_type == HallucinationType.SCHEMA
        ]
        assert any(m.span == "approved_by" for m in schema_mismatches), (
            f"approved_by must be reported as missing. Got: {outcome['verified'].mismatches}"
        )

    def test_invalid_enum_blocks_deploy(self):
        """
        Agent uses 'dev' as environment, which is not in the allowed enum.
        """
        _EXECUTION_LOG.clear()
        agent_args = {
            "service_name": "payment-service",
            "version": "v3.1.0",
            "environment": "dev",   # not in enum
            "approved_by": "jane.doe",
        }
        outcome = _agent_deploy_with_schema_gate(agent_args, self._DEPLOY_SCHEMA)

        assert outcome["executed"] is False, "Invalid enum value must block deployment"
        format_mismatches = [
            m for m in outcome["verified"].mismatches
            if m.hallucination_type == HallucinationType.FORMAT
        ]
        assert len(format_mismatches) >= 1, (
            f"Environment enum violation must be reported. Got: {outcome['verified'].mismatches}"
        )

    def test_valid_schema_allows_deploy(self):
        """
        All fields present and correct — deployment should proceed.
        """
        _EXECUTION_LOG.clear()
        agent_args = {
            "service_name": "payment-service",
            "version": "v3.1.0",
            "environment": "production",
            "approved_by": "jane.doe",
        }
        outcome = _agent_deploy_with_schema_gate(agent_args, self._DEPLOY_SCHEMA)

        assert outcome["executed"] is True, (
            f"Valid schema should allow deploy. Mismatches: {outcome['verified'].mismatches}"
        )
        assert len(_EXECUTION_LOG) == 1


class TestSessionDriftDetection:
    """Drift alert fires when an agent's reasoning quality degrades over turns."""

    def test_drift_alert_fires_after_degrading_scores(self):
        """
        Simulate 5 turns of an agent session where reasoning quality drops.
        After enough low-scoring turns, drift_alert must be True.
        """
        import uuid
        session_id = f"drift-test-{uuid.uuid4().hex[:8]}"

        # 3 consistent turns (high scores) followed by 2 inconsistent turns
        turns = [
            ("The payment was $100.", "The invoice total is $100."),
            ("Bob is the recipient.", "Funds go to Bob's account."),
            ("The job runs daily at midnight.", "The cron schedule is 0 0 * * *."),
            ("The refund is $5000.", "The original charge was $50."),   # hallucination
            ("Version 9.0 was deployed.", "Version 1.0 is in production."), # hallucination
        ]

        last_result = None
        for hyp, prem in turns:
            last_result = run_verification(
                hypothesis=hyp, premise=prem, session_id=session_id
            )

        # After 2 strong hallucinations, drift_alert should fire
        assert last_result is not None
        assert last_result.drift_alert is True, (
            f"Drift alert should fire after degrading scores. "
            f"session_mean={last_result.session_mean_score}"
        )

    def test_no_drift_on_consistent_session(self):
        """
        5 turns with consistently high factual scores → no drift alert.
        """
        import uuid
        session_id = f"nodrift-test-{uuid.uuid4().hex[:8]}"

        consistent_turns = [
            ("The payment was $100.", "The invoice total is $100."),
            ("The flight is at 6 AM.", "Departure is scheduled for 6:00 AM."),
            ("Bob receives the funds.", "Bob is the payee on the transaction."),
            ("Version 2.0 is live.", "The current production version is 2.0."),
            ("The job runs at midnight.", "The task is scheduled for 00:00 daily."),
        ]

        last_result = None
        for hyp, prem in consistent_turns:
            last_result = run_verification(
                hypothesis=hyp, premise=prem, session_id=session_id
            )

        assert last_result is not None
        assert last_result.drift_alert is False, (
            f"No drift expected on consistent session. "
            f"session_mean={last_result.session_mean_score}"
        )
