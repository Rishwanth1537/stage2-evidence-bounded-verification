import os
import yaml
from pathlib import Path

def _load_thresholds():
    config_path = Path(__file__).parent.parent / "configs" / "thresholds.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

_THRESHOLDS = _load_thresholds()

GED_THRESHOLD = float(_THRESHOLDS.get("ged_threshold", 0.35))
ENTAILMENT_THRESHOLD = float(_THRESHOLDS.get("entailment_threshold", 0.50))
GED_FAST_MODE_NODE_LIMIT = int(_THRESHOLDS.get("ged_fast_mode_node_limit", 80))

# Fail-closed on degraded mode (defaults to True; environment variable overrides)
_fail_closed_val = os.environ.get("FAIL_CLOSED_ON_DEGRADED")
if _fail_closed_val is not None:
    FAIL_CLOSED_ON_DEGRADED = _fail_closed_val.strip().lower() not in ("0", "false", "no", "off")
else:
    FAIL_CLOSED_ON_DEGRADED = bool(_THRESHOLDS.get("fail_closed_on_degraded", True))

# Two-tier gate policy configuration
_gp_dict = _THRESHOLDS.get("gate_policy", {})
_legacy_blocking_env = os.environ.get("GATE_POLICY_LEGACY_BLOCKING")
if _legacy_blocking_env is not None:
    GATE_POLICY_LEGACY_BLOCKING = _legacy_blocking_env.strip().lower() in ("1", "true", "yes", "on")
else:
    GATE_POLICY_LEGACY_BLOCKING = bool(_gp_dict.get("legacy_blocking", False))

GATE_POLICY_COVERAGE_FAIL_DECISION = os.environ.get(
    "GATE_POLICY_COVERAGE_FAIL_DECISION",
    str(_gp_dict.get("coverage_fail_decision", "ASK")).upper(),
)
GATE_POLICY_ORACLE_FAIL_DECISION = os.environ.get(
    "GATE_POLICY_ORACLE_FAIL_DECISION",
    str(_gp_dict.get("oracle_fail_decision", "BLOCK")).upper(),
)
