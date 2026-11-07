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
