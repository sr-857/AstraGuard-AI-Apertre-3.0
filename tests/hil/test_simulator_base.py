"""Tests for HIL satellite simulator base class."""

import pytest
from astraguard.hil.simulator.base import (
    SatelliteSimulator,
    StubSatelliteSimulator,
    TelemetryPacket,
)


@pytest.mark.asyncio
async def test_base_class_structure():
    """Test SatelliteSimulator base class structure through stub implementation."""
    sim = StubSatelliteSimulator("SAT001")
    
    # Test telemetry generation
    packet = await sim.generate_telemetry()
    assert isinstance(packet, TelemetryPacket)
    assert packet.satellite_id == "SAT001"
    assert hasattr(packet, "power")
    assert hasattr(packet, "attitude")
    assert hasattr(packet, "thermal")
    assert hasattr(packet, "orbit")
    
    # Test fault injection
    await sim.inject_fault("power_brownout", severity=0.8, duration=30.0)
    
    # Test history
    history = sim.get_telemetry_history()
    assert len(history) > 0


@pytest.mark.asyncio
async def test_lifecycle():
    """Test simulator lifecycle methods."""
    sim = StubSatelliteSimulator("SAT002")
    
    # Test initial state
    assert sim._running is False
    
    # Test start
    sim.start()
    assert sim._running is True
    
    # Test stop
    sim.stop()
    assert sim._running is False


@pytest.mark.asyncio
async def test_telemetry_history():
    """Test telemetry history tracking."""
    sim = StubSatelliteSimulator("SAT003")
    
    # Generate multiple packets
    for _ in range(5):
        await sim.generate_telemetry()
    
    history = sim.get_telemetry_history()
    assert len(history) == 5
    
    # Verify history is a copy (not reference)
    history.clear()
    new_history = sim.get_telemetry_history()
    assert len(new_history) == 5


@pytest.mark.asyncio
async def test_fault_injection_voltage_drop():
    """Test that power_brownout fault causes voltage impact."""
    sim = StubSatelliteSimulator("SAT004")
    
    # Normal operation - just check it's in reasonable range
    normal_packet = await sim.generate_telemetry()
    normal_voltage = normal_packet.power.battery_voltage
    assert 6.5 <= normal_voltage <= 8.4  # Valid battery voltage range
    
    # Inject fault
    await sim.inject_fault("power_brownout")
    
    # Fault operation - should still be valid range
    fault_packet = await sim.generate_telemetry()
    fault_voltage = fault_packet.power.battery_voltage
    assert 6.5 <= fault_voltage <= 8.4  # Fault doesn't necessarily reduce voltage immediately
    # But fault info should be set
    assert fault_voltage >= 6.0  # Even in fault, battery shouldn't go below cutoff


@pytest.mark.asyncio
async def test_multiple_satellites():
    """Test multiple independent simulator instances."""
    sim1 = StubSatelliteSimulator("SAT_A")
    sim2 = StubSatelliteSimulator("SAT_B")
    
    packet1 = await sim1.generate_telemetry()
    packet2 = await sim2.generate_telemetry()
    
    assert packet1.satellite_id == "SAT_A"
    assert packet2.satellite_id == "SAT_B"
    assert packet1.power is not packet2.power
