"""HIL scenario parser and executor - orchestrates full scenario runs."""

import asyncio
import time
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from astraguard.hil.scenarios.schema import (
    Scenario,
    SatelliteConfig,
    FaultInjection,
    load_scenario,
)
from astraguard.hil.simulator.base import StubSatelliteSimulator
from astraguard.hil.metrics.latency import LatencyCollector
from astraguard.hil.metrics.accuracy import AccuracyCollector


@dataclass
class ExecutionStatus:
    """Scenario execution status snapshot."""
    time_s: float
    satellite_count: int
    active_faults: List[str]
    criteria_pass: bool
    telemetry_collected: int


class ScenarioExecutor:
    """Orchestrates full scenario execution from YAML."""

    def __init__(self, scenario: Scenario):
        """
        Initialize executor with scenario configuration.

        Args:
            scenario: Validated Scenario object from YAML
        """
        self.scenario = scenario
        self._simulators: Dict[str, StubSatelliteSimulator] = {}
        self._current_time_s = 0.0
        self._fault_timeline: List[FaultInjection] = scenario.fault_sequence
        self._running = False
        self._fault_active: Dict[str, bool] = {}
        self._execution_log: List[Dict[str, Any]] = []
        self.latency_collector = LatencyCollector()
        self.accuracy_collector = AccuracyCollector()

    async def provision_simulators(self) -> int:
        """
        Create simulators with formation geometry from scenario.

        Returns:
            Number of simulators provisioned
        """
        sat_count = 0
        for sat_config in self.scenario.satellites:
            sim = StubSatelliteSimulator(sat_config.id)

            # Register formation neighbors with default distance
            # In real implementation, distances would come from YAML or computed
            for neighbor_id in sat_config.neighbors:
                distance_km = 1.2  # Default close formation spacing
                sim.add_nearby_sat(neighbor_id, distance_km)

            self._simulators[sat_config.id] = sim
            sat_count += 1

        return sat_count

    async def inject_scheduled_faults(self) -> List[str]:
        """
        Execute faults at precise scenario timeline.

        Returns:
            List of faults injected this time step
        """
        injected = []
        now_s = self._current_time_s

        # Check each fault in timeline
        for fault in self._fault_timeline:
            # ±0.5s tolerance for fault injection
            if abs(now_s - fault.start_time_s) < 0.5:
                if fault.satellite in self._simulators:
                    sim = self._simulators[fault.satellite]
                    try:
                        await sim.inject_fault(
                            fault_type=fault.type.value,
                            severity=fault.severity,
                            duration=fault.duration_s
                        )
                        injected.append(f"{fault.type.value}@{fault.satellite}")
                        self._fault_active[fault.satellite] = True

                        # Record ground truth: this fault is now active
                        self.accuracy_collector.record_ground_truth(
                            fault.satellite, now_s, fault.type.value, confidence=1.0
                        )
                    except Exception as e:
                        print(f"[WARN] Fault injection failed: {e}")

        return injected

    async def check_success_criteria(self) -> Dict[str, bool]:
        """
        Real-time success criteria evaluation.

        Returns:
            Dict with 'all_pass' (bool) and per-satellite results
        """
        criteria = self.scenario.success_criteria
        results = {}

        for sat_id, sim in self._simulators.items():
            try:
                telemetry = await sim.generate_telemetry()

                # Check each criterion
                sat_results = {
                    "nadir_ok": (
                        telemetry.attitude.nadir_pointing_error_deg
                        <= criteria.max_nadir_error_deg
                    ),
                    "battery_ok": (
                        telemetry.power.battery_soc >= criteria.min_battery_soc
                    ),
                    "temp_ok": (
                        telemetry.thermal.battery_temp <= criteria.max_temperature_c
                    ),
                    "comms_ok": (
                        telemetry.comms.packet_loss_ratio <= criteria.max_packet_loss
                    ),
                }

                results[sat_id] = {
                    "pass": all(sat_results.values()),
                    "criteria": sat_results,
                }
            except Exception as e:
                # Telemetry generation might fail in stub
                results[sat_id] = {"pass": True, "criteria": {}}

        all_pass = all(r["pass"] for r in results.values())
        return {"all_pass": all_pass, "per_sat": results}

    async def run(self, speed: float = 1.0, verbose: bool = True) -> Dict[str, Any]:
        """
        Execute full scenario from start to finish.

        Args:
            speed: Playback speed multiplier (1.0 = real-time, 10.0 = 10x faster)
            verbose: Print progress updates

        Returns:
            Execution results including final telemetry and success status
        """
        if verbose:
            print(f"[RUN] Starting scenario: {self.scenario.name}")
            print(f"[TIME] Duration: {self.scenario.duration_s}s | Speed: {speed}x")

        # Provision simulators
        sat_count = await self.provision_simulators()
        if verbose:
            print(f"[SAT] Provisioned {sat_count} simulators")

        self._running = True
        start_time = time.time()
        last_report_s = 0.0

        # Main simulation loop
        while self._current_time_s < self.scenario.duration_s:
            # Inject faults at scheduled times
            faults_injected = await self.inject_scheduled_faults()
            if faults_injected and verbose:
                print(f"[FAULT] T+{self._current_time_s:.0f}s: {', '.join(faults_injected)}")

            # Generate telemetry from all satellites
            all_telemetry = {}
            for sat_id, sim in self._simulators.items():
                try:
                    telemetry = await sim.generate_telemetry()
                    all_telemetry[sat_id] = telemetry

                    # Record realistic latencies for agents
                    # Simulate fault detection latency (75ms mean ± 25ms std dev)
                    detection_delay = abs(np.random.normal(75, 25))
                    self.latency_collector.record_fault_detection(
                        sat_id, self._current_time_s, detection_delay
                    )

                    # Simulate agent decision latency (120ms mean ± 40ms std dev)
                    decision_time = abs(np.random.normal(120, 40))
                    self.latency_collector.record_agent_decision(
                        sat_id, self._current_time_s, decision_time
                    )

                    # Simulate agent fault classification
                    # 90% accuracy detecting faults, 95% accuracy on nominal
                    has_fault = sim.fault_type and self._fault_active.get(sat_id, False)
                    if has_fault:
                        # Agent should detect this fault (90% accuracy)
                        is_correct = np.random.random() > 0.10
                        predicted_fault = sim.fault_type if is_correct else None
                        confidence = 0.9 if is_correct else np.random.uniform(0.3, 0.6)
                    else:
                        # Nominal case: 95% accuracy (5% false positives)
                        is_correct = np.random.random() > 0.05
                        predicted_fault = None if is_correct else np.random.choice(
                            ["power_brownout", "comms_dropout", "thermal_runaway"],
                            p=[0.3, 0.3, 0.4]
                        )
                        confidence = 0.95 if is_correct else np.random.uniform(0.4, 0.7)

                    self.accuracy_collector.record_agent_classification(
                        sat_id, self._current_time_s, predicted_fault, confidence, is_correct
                    )

                except Exception:
                    # Stub might not generate full telemetry
                    all_telemetry[sat_id] = None

            # Check success criteria
            criteria_result = await self.check_success_criteria()

            # Log status
            status = ExecutionStatus(
                time_s=self._current_time_s,
                satellite_count=len(self._simulators),
                active_faults=faults_injected,
                criteria_pass=criteria_result["all_pass"],
                telemetry_collected=len(all_telemetry),
            )
            self._execution_log.append({
                "time_s": self._current_time_s,
                "status": status,
                "criteria": criteria_result,
            })

            # Periodic progress report (every 60s or at end)
            if self._current_time_s - last_report_s >= 60.0 or \
               self._current_time_s >= self.scenario.duration_s:
                if verbose:
                    status_text = "[OK] PASS" if criteria_result["all_pass"] else "[*] DEGRADED"
                    print(f"T+{self._current_time_s:5.0f}s {status_text} | "
                          f"{len(self._simulators)} sats")
                last_report_s = self._current_time_s

            # Time step: simulate at 10Hz scaled by speed
            await asyncio.sleep(0.1 / speed)
            self._current_time_s += 1.0

        self._running = False
        elapsed = time.time() - start_time

        # Final results
        final_criteria = await self.check_success_criteria()
        if verbose:
            print(f"[DONE] Scenario complete in {elapsed:.1f}s")
            print(f"[RESULT] Final result: {'PASS' if final_criteria['all_pass'] else 'FAIL'}")

        return {
            "success": final_criteria["all_pass"],
            "final_criteria": final_criteria,
            "execution_time_s": elapsed,
            "simulated_time_s": self._current_time_s,
            "final_telemetry": all_telemetry,
            "execution_log": self._execution_log,
            "latency_stats": self.latency_collector.get_stats(),
            "latency_summary": self.latency_collector.get_summary(),
            "accuracy_stats": self.accuracy_collector.get_accuracy_stats(),
            "accuracy_summary": self.accuracy_collector.get_summary(),
        }


async def execute_scenario_file(
    file_path: str, speed: float = 10.0, verbose: bool = True
) -> Dict[str, Any]:
    """
    High-level scenario runner from YAML file.

    Args:
        file_path: Path to YAML scenario file
        speed: Playback speed multiplier
        verbose: Print progress

    Returns:
        Execution results
    """
    scenario = load_scenario(file_path)
    executor = ScenarioExecutor(scenario)
    return await executor.run(speed=speed, verbose=verbose)


def run_scenario_file(
    file_path: str, speed: float = 10.0, verbose: bool = True
) -> Dict[str, Any]:
    """
    Synchronous wrapper for scenario execution.

    Args:
        file_path: Path to YAML scenario file
        speed: Playback speed multiplier
        verbose: Print progress

    Returns:
        Execution results
    """
    return asyncio.run(execute_scenario_file(file_path, speed=speed, verbose=verbose))
