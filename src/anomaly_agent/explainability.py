from typing import Dict, Any

def build_explanation(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "primary_factor": context.get("primary_factor", "Policy-based anomaly decision"),
        "secondary_factors": context.get("secondary_factors", []),
        "mission_phase_constraint": context.get("mission_phase", "UNKNOWN"),
        "confidence": float(context.get("confidence", 0.0))
    }
