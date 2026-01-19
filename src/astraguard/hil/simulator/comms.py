"""
Realistic S-band communications simulator with Gilbert-Elliot channel model.

Models:
- S-band (2.4 GHz) link budget with free space path loss
- Gilbert-Elliot state machine for bursty dropout patterns
- Power coupling: brownout (<7V) causes TX power derating + packet loss
- Range-dependent signal degradation (>800km = near blackout)
- Realistic packet loss for swarm message passing
"""

import numpy as np
from enum import Enum
from typing import Dict, Any


class CommsState(Enum):
    """Comms link state."""
    NOMINAL = "nominal"      # <2% loss, good TX power
    DEGRADED = "degraded"    # 2-30% loss, reduced TX or high range
    DROPOUT = "dropout"      # >30% loss or bad Gilbert state


class CommsSimulator:
    """S-band communications system with realistic link budget and fading."""
    
    def __init__(self, sat_id: str):
        """
        Initialize comms system.
        
        Args:
            sat_id: Satellite identifier
        """
        self.sat_id = sat_id
        
        # Link state
        self.state = CommsState.NOMINAL
        self.packet_loss_rate = 0.02  # 2% baseline at nominal
        self.tx_power_dbw = 2.0        # 2W S-band transmitter
        
        # Gilbert-Elliot state machine for bursty fading
        # Good state (95% hold) → Bad state (90% escape to good)
        self._gilbert_state = True  # True = good state, False = bad state
        self._gilbert_good_prob = 0.95   # Stay in good state
        self._gilbert_bad_prob = 0.10    # Escape bad state back to good
        
        # Range and path loss
        self.range_km = 500.0  # Default ground station distance
        self.tx_antenna_gain_dbi = 3.0  # Omnidirectional element
        self.rx_antenna_gain_dbi = 40.0  # Large ground station array
        
    def update(self, power_voltage: float, range_km: float = 500.0, dt: float = 1.0):
        """
        Update comms state based on power and range.
        
        Args:
            power_voltage: Battery voltage (V) - drives TX power
            range_km: Ground station distance (km)
            dt: Time step (s) - for state machine updates
        """
        self.range_km = range_km
        
        # TX Power Derating with Brownout
        # Nominal: 7.4V → 2.0W (8.0 dBm)
        # Brownout: 6.5V → 1.0W (0.0 dBm) - 50% reduction
        # Critical: 6.0V → 0.5W (-3.0 dBm) - 75% reduction
        if power_voltage < 6.5:
            # Deep brownout: TX power reduced
            tx_factor = max(0.01, (power_voltage - 6.0) / 1.4)  # Prevent log(0)
            self.tx_power_dbw = -3.0 + (10.0 * np.log10(tx_factor))
        elif power_voltage < 7.2:
            # Brownout: TX power derating
            tx_factor = max(0.01, (power_voltage - 6.5) / 0.7)  # Prevent log(0)
            self.tx_power_dbw = 0.0 + (2.0 * np.log10(tx_factor))
        else:
            # Nominal: Full power
            self.tx_power_dbw = 2.0
        
        # Packet Loss from Brownout
        # Nominal: 2% loss
        # Brownout: 30% loss at <7.0V
        # Critical: 80% loss at <6.0V
        if power_voltage < 6.5:
            brownout_loss = 0.80 - (power_voltage - 6.0) / 0.5 * 0.5  # 0.5-0.8
            self.packet_loss_rate = min(0.85, brownout_loss)
        elif power_voltage < 7.2:
            brownout_loss = 0.30 - (power_voltage - 6.5) / 0.7 * 0.28  # 0.02-0.3
            self.packet_loss_rate = brownout_loss
        else:
            self.packet_loss_rate = 0.02
        
        # Free Space Path Loss (S-band 2.4 GHz)
        # FSPL(dB) = 32.44 + 20*log10(f_MHz) + 20*log10(d_km)
        # At 2400 MHz: FSPL = 32.44 + 67.56 + 20*log10(range_km)
        fspl_db = 100.0 + 20.0 * np.log10(max(0.1, range_km))
        
        # Link margin = TX + RX_gain - FSPL - losses
        # Typical margin at 500km: 2 + 40 - 147 - 5(rain) = -110 dBm (good)
        link_margin_db = (self.tx_power_dbw + self.rx_antenna_gain_dbi + 
                         self.tx_antenna_gain_dbi - fspl_db - 10.0)  # 10dB system margin
        
        # Range-based packet loss
        # >700km: Degraded (5% baseline)
        # >800km: Dropout (50% baseline)
        # >900km: Near blackout (90% baseline)
        range_loss_factor = 0.02
        if range_km > 700:
            range_loss_factor = 0.05
        if range_km > 800:
            range_loss_factor = 0.50
        if range_km > 900:
            range_loss_factor = 0.90
        
        self.packet_loss_rate = min(0.95, self.packet_loss_rate + range_loss_factor)
        
        # Gilbert-Elliot state machine - models bursty fading
        if self._gilbert_state:  # Currently in Good state
            # Probability of staying good
            if np.random.random() > self._gilbert_good_prob:
                self._gilbert_state = False  # Transition to bad state
                # Bad state loss is high
                self.packet_loss_rate = min(0.90, self.packet_loss_rate + 0.35)
        else:  # Currently in Bad state
            # Probability of escaping to good state
            if np.random.random() < self._gilbert_bad_prob:
                self._gilbert_state = True  # Transition to good state
                # Reduce loss when back in good state
                self.packet_loss_rate = max(0.02, self.packet_loss_rate - 0.25)
        
        # Determine overall state
        if self.packet_loss_rate > 0.30:
            self.state = CommsState.DROPOUT
        elif self.packet_loss_rate > 0.02:
            self.state = CommsState.DEGRADED
        else:
            self.state = CommsState.NOMINAL
    
    def transmit_packet(self) -> bool:
        """
        Simulate packet transmission success/failure.
        
        Returns:
            True if packet successfully transmitted, False if dropped
        """
        if self.state == CommsState.DROPOUT:
            return False
        
        return np.random.random() > self.packet_loss_rate
    
    def get_comms_stats(self) -> Dict[str, Any]:
        """
        Get current comms system statistics.
        
        Returns:
            Dict with state, loss rate, TX power, and Gilbert state
        """
        return {
            "state": self.state.value,
            "packet_loss_rate": round(self.packet_loss_rate, 3),
            "tx_power_dbw": round(self.tx_power_dbw, 1),
            "gilbert_state": "good" if self._gilbert_state else "bad",
            "range_km": round(self.range_km, 1),
        }
    
    def get_status(self) -> str:
        """Get human-readable comms status."""
        state_emoji = {
            CommsState.NOMINAL: "NOMINAL",
            CommsState.DEGRADED: "DEGRADED",
            CommsState.DROPOUT: "DROPOUT"
        }
        return f"{state_emoji[self.state]}: {self.packet_loss_rate:.1%} loss, {self.tx_power_dbw:.1f} dBW"
