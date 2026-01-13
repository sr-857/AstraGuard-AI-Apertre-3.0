"""
Contagious thermal runaway cascade across CubeSat formation.

Models radiator failure as a spreading infection through nearby satellites,
enabling testing of formation thermal resilience and coordinated recovery policies.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import numpy as np


@dataclass
class NeighborProximity:
    """Formation neighbor tracking for cascade propagation."""
    sat_id: str
    distance_km: float
    contagion_risk: float = 1.0  # 0-1, 1.0 = susceptible


class ThermalRunawayFault:
    """
    Contagious thermal runaway fault model.
    
    Simulates radiator failure as primary infection that propagates
    to nearby satellites through heat coupling in formation flying.
    
    Physics model:
    - Primary: Radiator capacity drops to 10% (0.1x multiplier)
    - Contagion: Distance-dependent infection probability
    - Heat coupling: Infected neighbors add 2-5W ambient heat
    - Recovery: Fault expires after configured duration
    """
    
    def __init__(
        self, 
        sat_id: str, 
        contagion_rate: float = 0.2, 
        duration: float = 600.0
    ):
        """
        Initialize thermal runaway fault.
        
        Args:
            sat_id: Satellite identifier
            contagion_rate: Base infection probability (0.05-0.8, clamped)
            duration: Fault duration in seconds (300-1800)
        """
        self.sat_id = sat_id
        self.contagion_rate = np.clip(contagion_rate, 0.05, 0.8)
        self.duration = np.clip(duration, 0.1, 1800.0)
        self.start_time: Optional[datetime] = None
        self.active = False
        self.infected_neighbors: List[str] = []
        
    def inject(self) -> None:
        """
        Activate primary thermal runaway infection.
        
        Triggers radiator failure and starts countdown to recovery.
        """
        self.start_time = datetime.now()
        self.active = True
        
    def infect_neighbor(self, neighbor: NeighborProximity) -> bool:
        """
        Attempt contagion to nearby satellite.
        
        Distance-based infection probability:
        - <2km (close formation): ~40% per update
        - 2-3km (medium): ~20% per update
        - 3-5km (loose formation): ~8% per update
        - >5km: No infection (formation limit)
        
        Args:
            neighbor: NeighborProximity with sat_id, distance_km, contagion_risk
            
        Returns:
            True if infection succeeds, False otherwise
        """
        if neighbor.distance_km > 5.0:
            return False
        
        if neighbor.sat_id in self.infected_neighbors:
            return False  # Already infected
        
        # Distance-based risk: closer = higher risk
        # risk(d) = contagion_rate * (1 - d/5.0) * contagion_risk
        # At 1km: risk = contagion_rate * 0.8
        # At 3km: risk = contagion_rate * 0.4
        # At 5km: risk = contagion_rate * 0.0 (but filtered above)
        distance_factor = 1.0 - (neighbor.distance_km / 5.0)
        infection_prob = self.contagion_rate * distance_factor * neighbor.contagion_risk
        
        return np.random.random() < infection_prob
    
    def is_expired(self) -> bool:
        """
        Check if thermal runaway has completed its duration.
        
        Returns:
            True if fault has expired or never injected, False if still active
        """
        if not self.active or not self.start_time:
            return True
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.duration
    
    def get_fault_state(self) -> Dict[str, Any]:
        """
        Get diagnostic state of thermal runaway fault.
        
        Returns:
            Dict with keys:
            - active: bool, is fault currently active
            - contagion_rate: float, base infection probability
            - infected_count: int, number of infected neighbors
            - infected_neighbors: list of sat_ids that got infected
            - time_remaining_s: float, seconds until auto-recovery
            - time_elapsed_s: float, seconds since injection
        """
        if not self.start_time:
            time_remaining = 0.0
            time_elapsed = 0.0
        else:
            time_elapsed = (datetime.now() - self.start_time).total_seconds()
            time_remaining = max(0.0, self.duration - time_elapsed)
        
        return {
            "active": self.active,
            "contagion_rate": self.contagion_rate,
            "infected_count": len(self.infected_neighbors),
            "infected_neighbors": self.infected_neighbors.copy(),
            "time_remaining_s": time_remaining,
            "time_elapsed_s": time_elapsed,
        }
