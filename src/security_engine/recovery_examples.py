"""Example recovery functions decorated with @log_feedback.

This module demonstrates how to apply @log_feedback decorator to
existing recovery functions in the system. Decorators can be applied
to any recovery action without modifying the underlying logic.
"""

from security_engine.decorators import log_feedback


# Example 1: Power subsystem recovery
@log_feedback(fault_id="power_loss_001", anomaly_type="power_subsystem")
def emergency_power_cycle(system_state) -> bool:
    """Emergency power cycle for power subsystem recovery.
    
    This function would contain the actual power cycling logic.
    The @log_feedback decorator automatically captures the result.
    """
    # Recovery logic would go here
    return True  # Placeholder: actual implementation returns bool


# Example 2: Thermal subsystem recovery
@log_feedback(fault_id="thermal_spike_001", anomaly_type="thermal_subsystem")
def activate_passive_cooling(system_state) -> bool:
    """Activate passive cooling to manage thermal spikes.
    
    The decorator captures:
    - Whether the action succeeded (True/False)
    - The mission_phase from system_state if available
    - Confidence score (1.0 for success, 0.5 for failure)
    """
    # Thermal control logic would go here
    return True  # Placeholder


# Example 3: Communication recovery
@log_feedback(
    fault_id="comms_loss_001", anomaly_type="communication_subsystem"
)
def reinitialize_communication(system_state) -> bool:
    """Reinitialize communication subsystem after anomaly.
    
    Each decorated function will:
    1. Execute the original logic
    2. Automatically create a FeedbackEvent
    3. Append to feedback_pending.json
    4. Continue execution (non-blocking)
    """
    # Communication recovery logic would go here
    return True  # Placeholder


# Example 4: State recovery
@log_feedback(fault_id="state_corruption_001", anomaly_type="state_anomaly")
def reset_system_state(system_state) -> bool:
    """Reset system state to last known good configuration.
    
    Non-blocking behavior: Even if feedback logging fails,
    the recovery action completes and returns its original value.
    """
    # State recovery logic would go here
    return True  # Placeholder


if __name__ == "__main__":
    # Example usage
    class MockSystemState:
        """Mock system state for demonstration."""
        mission_phase = "NOMINAL_OPS"
        temperature = 45.2
        voltage = 7.5

    state = MockSystemState()
    
    # These would normally be called by the recovery orchestrator
    # Each call will auto-log a FeedbackEvent to feedback_pending.json
    result1 = emergency_power_cycle(state)
    result2 = activate_passive_cooling(state)
    result3 = reinitialize_communication(state)
    result4 = reset_system_state(state)
    
    print(f"Power cycle: {result1}")
    print(f"Passive cooling: {result2}")
    print(f"Comms reinitialized: {result3}")
    print(f"State reset: {result4}")
