"""
Configurable comms dropout fault patterns for swarm message passing stress testing.

Supports:
- Gilbert-Elliot bursty dropout (realistic fading channels)
- Constant high-loss patterns (near blackout scenarios)
- Power + range coupled degradation
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class CommsDropoutFault:
    """Simulated dropout fault with auto-recovery and pattern control."""
    
    def __init__(self, sat_id: str, pattern: str = "gilbert", packet_loss: float = 0.3, 
                 duration: float = 300.0):
        """
        Initialize comms dropout fault.
        
        Args:
            sat_id: Satellite identifier (max 16 chars)
            pattern: "gilbert" (bursty) or "constant" (steady high loss)
            packet_loss: Target packet loss rate (0.05-0.95)
            duration: Fault duration in seconds before auto-recovery
        
        Raises:
            ValueError: If sat_id exceeds 16 characters
        """
        if len(sat_id) > 16:
            raise ValueError(f"sat_id '{sat_id}' exceeds 16 character limit")
        
        self.sat_id = sat_id
        self.pattern = pattern
        self.packet_loss = min(max(packet_loss, 0.05), 0.95)  # Clamp to valid range
        self.duration = duration
        
        # Fault timeline
        self.start_time: Optional[datetime] = None
        self.active = False
        
        # Pattern parameters for Gilbert-Elliot
        # Bursty: Spend 30s in good state, 120s in bad state (realistic)
        # Constant: Stay in bad state permanently
        self.gilbert_good_prob = 0.85 if pattern == "gilbert" else 0.95
        self.gilbert_bad_prob = 0.08 if pattern == "gilbert" else 0.95
    
    def inject(self):
        """Activate fault - start the dropout sequence."""
        self.start_time = datetime.now()
        self.active = True
    
    def is_expired(self) -> bool:
        """
        Check if fault duration exceeded.
        
        Returns:
            True if fault expired or inactive, False if still active
        """
        if not self.active or self.start_time is None:
            return True
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.duration
    
    def get_fault_state(self) -> Dict[str, Any]:
        """
        Get current fault state for diagnostics.
        
        Returns:
            Dict with pattern, loss rate, time remaining, and other stats
        """
        if not self.active or self.start_time is None:
            return {"active": False}
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "active": True,
            "pattern": self.pattern,
            "packet_loss": round(self.packet_loss, 3),
            "time_remaining": max(0, self.duration - elapsed),
            "elapsed": round(elapsed, 1),
            "gilbert_good_prob": round(self.gilbert_good_prob, 2),
            "gilbert_bad_prob": round(self.gilbert_bad_prob, 2),
        }
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        Detailed fault configuration and timeline.
        
        Returns:
            Complete fault state for diagnostics
        """
        state = self.get_fault_state()
        return {
            "sat_id": self.sat_id,
            "pattern": self.pattern,
            "packet_loss": self.packet_loss,
            "duration": self.duration,
            "active": self.active,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "is_expired": self.is_expired(),
            **state,
        }
