"""Configurable power brownout fault patterns for HIL testing.

This module implements realistic power brownout fault scenarios for CubeSat swarms:
- Phase 1 (0-60s): Solar panel degradation (60-90% efficiency loss)
- Phase 2 (60-180s): Battery discharge acceleration (1.5-2.5x faster)
- Phase 3 (180s+): Safe-mode load spike (8W high-power recovery attempts)

Severity scaling:
- 0.1: Minor degradation (60% panel loss, 1.5x discharge)
- 0.5: Medium fault (75% panel loss, 2.0x discharge)
- 0.9: Severe brownout (90% panel loss, 2.5x discharge)
- 1.0: Catastrophic (same as 0.9, clamped)

Auto-recovery:
- Fault automatically expires after duration
- Simulator restores nominal power parameters
- Tests swarm resilience to temporary power crises
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class PowerBrownoutFault:
    """Multi-phase brownout: panel damage → battery stress → safe mode.
    
    Attributes:
        sat_id: Satellite identifier
        severity: Fault intensity (0.1-1.0), affects all phases
        duration: Total fault duration (seconds)
        start_time: When fault was injected (datetime)
        active: Whether fault is currently active (bool)
        panel_damage_factor: Solar panel efficiency multiplier (0.1-0.4)
        discharge_multiplier: Battery discharge rate multiplier (1.5-2.5)
        safe_mode_load_w: High-power load during recovery phase (8W)
    """
    
    def __init__(self, sat_id: str, severity: float = 1.0, duration: float = 300.0):
        """Initialize brownout fault.
        
        Args:
            sat_id: Satellite identifier (max 16 chars)
            severity: Fault severity (0.1-1.0), affects degradation intensity
            duration: How long fault lasts before auto-recovery (seconds)
        
        Raises:
            ValueError: If sat_id exceeds 16 characters
        """
        if len(sat_id) > 16:
            raise ValueError(f"sat_id '{sat_id}' exceeds 16 character limit")
        
        self.sat_id = sat_id
        
        # Clamp severity to valid range
        self.severity = min(max(severity, 0.1), 1.0)
        self.duration = duration
        
        # Timeline tracking
        self.start_time: Optional[datetime] = None
        self.active = False
        
        # Phase 1: Solar panel degradation
        # Severity 0.1 → 60% efficiency loss (multiply by 0.4)
        # Severity 1.0 → 90% efficiency loss (multiply by 0.1)
        # Linear interpolation: 0.4 - 0.3*severity = 0.4 to 0.1
        self.panel_damage_factor = 0.4 - (self.severity * 0.3)
        
        # Phase 2: Battery discharge acceleration
        # Severity 0.1 → 1.5x faster discharge
        # Severity 1.0 → 2.5x faster discharge
        # Linear: 1.5 + 1.0*severity = 1.5 to 2.5
        self.discharge_multiplier = 1.5 + (self.severity * 1.0)
        
        # Phase 3: Safe-mode load spike
        # Constant 8W recovery attempts when power critically low
        self.safe_mode_load_w = 8.0
        
        # Fault state for diagnostics
        self._phase_transitions = {
            "panel_damage": 0.0,
            "battery_stress": 60.0,
            "safe_mode": 180.0,
        }
    
    def inject(self):
        """Trigger brownout sequence start.
        
        Sets start_time to now and activates fault.
        Fault will propagate through 3 phases over duration seconds.
        """
        self.start_time = datetime.now()
        self.active = True
    
    def is_expired(self) -> bool:
        """Check if fault duration exceeded.
        
        Returns:
            True if fault has expired or was never injected, False if still active
        """
        if not self.active or self.start_time is None:
            return True
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.duration
    
    def get_fault_state(self) -> Dict[str, Any]:
        """Current brownout parameters for simulator.
        
        Returns:
            Dict with current phase, degradation factors, and remaining time
            Returns {"active": False} if fault not active
        
        Phase progression:
        - panel_damage (0-60s): Solar panel degradation dominates
        - battery_stress (60-180s): Battery discharge accelerates
        - safe_mode (180s+): High-power recovery loads kick in
        """
        if not self.active or self.start_time is None:
            return {"active": False}
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Determine current phase
        if elapsed < 60:
            phase = "panel_damage"
        elif elapsed < 180:
            phase = "battery_stress"
        else:
            phase = "safe_mode"
        
        return {
            "active": True,
            "phase": phase,
            "panel_damage_factor": self.panel_damage_factor,
            "discharge_multiplier": self.discharge_multiplier,
            "safe_mode_load": self.safe_mode_load_w if phase == "safe_mode" else 0.0,
            "time_remaining": max(0, self.duration - elapsed),
            "elapsed": elapsed,
            "severity": self.severity,
        }
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Return detailed fault state for diagnostics.
        
        Returns:
            Dict with complete fault configuration and timeline
        """
        state = self.get_fault_state()
        return {
            "sat_id": self.sat_id,
            "severity": self.severity,
            "duration": self.duration,
            "active": self.active,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "is_expired": self.is_expired(),
            "panel_damage_factor": self.panel_damage_factor,
            "discharge_multiplier": self.discharge_multiplier,
            "safe_mode_load_w": self.safe_mode_load_w,
            **state,
        }
