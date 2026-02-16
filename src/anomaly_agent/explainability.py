"""
Explainability Module

Provides utilities to build human-readable explanations for anomaly decisions.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def build_explanation(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a structured explanation dictionary from anomaly decision context.
    
    Args:
        context: Dictionary containing:
            - primary_factor (str, optional): Main reason for decision
            - secondary_factors (list, optional): Additional contributing factors
            - mission_phase (str, optional): Current mission phase
            - confidence (float, optional): Confidence score (0.0-1.0)
    
    Returns:
        Dictionary with explanation fields
    
    Raises:
        ValueError: If context is None or critical validation fails
        TypeError: If context is not a dictionary
    
    Example:
        >>> context = {
        ...     "primary_factor": "High thermal reading",
        ...     "secondary_factors": ["Recurrence: 3", "Duration: 120s"],
        ...     "mission_phase": "ORBIT",
        ...     "confidence": 0.85
        ... }
        >>> explanation = build_explanation(context)
    """
    # Input validation: check for None
    if context is None:
        logger.error("build_explanation called with None context")
        raise ValueError("Context cannot be None")
    
    # Input validation: check for dict type
    if not isinstance(context, dict):
        logger.error(
            f"build_explanation called with invalid type: {type(context).__name__} "
            f"(expected dict)"
        )
        raise TypeError(f"Context must be a dict, got {type(context).__name__}")
    
    # Warn on empty context
    if not context:
        logger.warning("build_explanation called with empty context dict, using all defaults")
    
    # Extract and validate primary_factor
    primary_factor = context.get("primary_factor", "Policy-based anomaly decision")
    if not isinstance(primary_factor, str):
        logger.warning(
            f"primary_factor is not a string (got {type(primary_factor).__name__}), "
            f"converting to string"
        )
        primary_factor = str(primary_factor)
    
    # Extract and validate secondary_factors
    secondary_factors = context.get("secondary_factors", [])
    if not isinstance(secondary_factors, list):
        logger.warning(
            f"secondary_factors is not a list (got {type(secondary_factors).__name__}), "
            f"wrapping in list"
        )
        secondary_factors = [secondary_factors] if secondary_factors else []
    
    # Extract and validate mission_phase
    mission_phase = context.get("mission_phase", "UNKNOWN")
    if not isinstance(mission_phase, str):
        logger.warning(
            f"mission_phase is not a string (got {type(mission_phase).__name__}), "
            f"converting to string"
        )
        mission_phase = str(mission_phase)
    
    # Extract and validate confidence (most critical validation)
    confidence_raw = context.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
        
        # Warn if confidence is outside expected range
        if not (0.0 <= confidence <= 1.0):
            logger.warning(
                f"Confidence value {confidence} is outside expected range [0.0, 1.0]. "
                f"This may indicate a data quality issue."
            )
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid confidence value: {confidence_raw!r} "
            f"(expected numeric value between 0.0-1.0)"
        )
        raise ValueError(
            f"Invalid confidence value: {confidence_raw!r}, must be numeric"
        ) from e
    
    # Log successful explanation build (debug level)
    logger.debug(
        f"Built explanation: phase={mission_phase}, "
        f"confidence={confidence:.2f}, "
        f"factors={len(secondary_factors)}"
    )
    
    return {
        "primary_factor": primary_factor,
        "secondary_factors": secondary_factors,
        "mission_phase_constraint": mission_phase,
        "confidence": confidence
    }
