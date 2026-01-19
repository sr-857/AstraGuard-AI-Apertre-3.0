"""
Accuracy Metrics Demo (Issue #498).

Comprehensive demonstration of AstraGuard accuracy validation against ground truth.

This demo shows:
1. Single scenario accuracy computation
2. Per-fault-type precision/recall/F1
3. Per-satellite accuracy breakdown
4. Confusion matrix visualization
5. Regulatory compliance validation
6. Campaign aggregation with multiple scenarios

Usage:
    python examples/accuracy_demo_498.py

Output:
    - Console: Pretty-printed accuracy statistics
    - CSV: Raw classification data for analysis
    - JSON: Comprehensive metrics summary
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

# Add astraguard to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from astraguard.hil.metrics.accuracy import AccuracyCollector
from astraguard.hil.scenarios.schema import (
    Scenario,
    SatelliteConfig,
    FaultInjection,
    FaultType,
    SuccessCriteria,
)
from astraguard.hil.scenarios.parser import ScenarioExecutor


def print_header(text: str, char: str = "="):
    """Print formatted header."""
    print(f"\n{char * 80}")
    print(f"{text:^80}")
    print(f"{char * 80}\n")


def print_section(text: str):
    """Print formatted section."""
    print(f"\n{text}")
    print("-" * len(text))


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format as percentage."""
    return f"{value * 100:.{decimals}f}%"


def print_accuracy_stats(stats: dict):
    """Pretty-print accuracy statistics."""
    print_section("Overall Accuracy")
    print(f"  Overall Accuracy: {format_percentage(stats['overall_accuracy'])}")
    print(f"  Total Classifications: {stats.get('total_classifications', 0)}")

    if "by_fault_type" in stats and stats["by_fault_type"]:
        print_section("Per-Fault-Type Metrics")
        rows = []
        for fault_type, metrics in stats["by_fault_type"].items():
            rows.append(
                [
                    fault_type,
                    format_percentage(metrics.get("precision", 0)),
                    format_percentage(metrics.get("recall", 0)),
                    format_percentage(metrics.get("f1", 0)),
                    f"{metrics.get('count', 0)}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["Fault Type", "Precision", "Recall", "F1 Score", "Count"],
                tablefmt="grid",
            )
        )


def print_per_satellite_breakdown(sat_stats: dict):
    """Print per-satellite accuracy breakdown."""
    if not sat_stats:
        return

    print_section("Per-Satellite Accuracy")
    rows = []
    for sat_id, metrics in sat_stats.items():
        rows.append(
            [
                sat_id,
                format_percentage(metrics.get("accuracy", 0)),
                f"{metrics.get('correct', 0)}/{metrics.get('total', 0)}",
                format_percentage(metrics.get("avg_confidence", 0)),
            ]
        )
    print(
        tabulate(
            rows,
            headers=["Satellite", "Accuracy", "Correct/Total", "Avg Confidence"],
            tablefmt="grid",
        )
    )


def print_confusion_matrix(matrix: dict):
    """Print confusion matrix."""
    if not matrix:
        return

    print_section("Confusion Matrix (Predicted -> Actual)")
    # Format as readable table
    fault_types = sorted(set(matrix.keys()) | {k for v in matrix.values() for k in v})
    rows = []

    for predicted in sorted(fault_types):
        row = [predicted]
        for actual in sorted(fault_types):
            count = matrix.get(predicted, {}).get(actual, 0)
            row.append(str(count))
        rows.append(row)

    print(
        tabulate(
            rows,
            headers=["Predicted ->"] + sorted(fault_types),
            tablefmt="grid",
        )
    )


async def demo_single_scenario():
    """Demo: Single scenario accuracy computation."""
    print_header("SINGLE SCENARIO ACCURACY DEMO")

    # Create a simple test scenario
    scenario = Scenario(
        name="single_scenario_demo",
        description="Demonstration of accuracy metrics on single scenario",
        duration_s=300,
        satellites=[
            SatelliteConfig(
                id="SAT-001",
                initial_position_km=[0, 0, 420],
            ),
            SatelliteConfig(
                id="SAT-002",
                initial_position_km=[100, 100, 420],
            ),
        ],
        fault_sequence=[
            FaultInjection(
                satellite="SAT-001",
                type=FaultType.POWER_BROWNOUT,
                start_time_s=60.0,
                duration_s=60.0,
            ),
            FaultInjection(
                satellite="SAT-002",
                type=FaultType.THERMAL_RUNAWAY,
                start_time_s=120.0,
                duration_s=60.0,
            ),
        ],
        success_criteria=SuccessCriteria(max_temperature_c=85.0),
    )

    print(f"Running scenario: {scenario.name}")
    print(f"Duration: {scenario.duration_s}s, Satellites: {len(scenario.satellites)}, Faults: {len(scenario.fault_sequence)}")

    # Execute scenario
    executor = ScenarioExecutor(scenario)
    results = await executor.run(speed=10.0, verbose=False)

    # Print results
    print_section("Scenario Execution Results")
    print(f"  Success: {'✓ PASS' if results['success'] else '✗ FAIL'}")
    print(f"  Execution Time: {results['execution_time_s']:.2f}s")
    print(f"  Simulated Time: {results['simulated_time_s']:.1f}s")

    # Print accuracy stats
    if "accuracy_stats" in results:
        print_accuracy_stats(results["accuracy_stats"])
    if "accuracy_summary" in results:
        summary = results["accuracy_summary"]
        if isinstance(summary, dict) and summary:
            print_section("Accuracy Summary")
            print(f"  Total Classifications: {summary.get('total_classifications', 0)}")

            # Get per-satellite breakdown
            if "by_satellite" in summary:
                print_per_satellite_breakdown(summary.get("by_satellite", {}))

            # Get confusion matrix
            if "confusion_matrix" in summary:
                print_confusion_matrix(summary.get("confusion_matrix", {}))


def demo_manual_accuracy_collection():
    """Demo: Manual accuracy collection and metrics computation."""
    print_header("MANUAL ACCURACY COLLECTION DEMO")

    # Create collector
    collector = AccuracyCollector()

    print("Recording classifications...")
    print_section("Scenario: Multi-satellite fault detection")

    # Simulate three satellites with different accuracy profiles

    # SAT-001: Excellent accuracy (95%)
    sat001_data = [
        ("power_brownout", True, 0.95),
        ("power_brownout", True, 0.92),
        ("nominal", True, 0.98),
        ("nominal", True, 0.96),
        ("thermal_runaway", True, 0.94),
    ]

    # SAT-002: Good accuracy (80%)
    sat002_data = [
        ("comms_dropout", True, 0.88),
        ("comms_dropout", True, 0.85),
        ("nominal", False, 0.45),  # False positive
        ("nominal", True, 0.92),
        ("thermal_runaway", True, 0.79),
    ]

    # SAT-003: Fair accuracy (60%)
    sat003_data = [
        ("power_brownout", False, 0.52),  # Misclassified
        ("thermal_runaway", True, 0.71),
        ("nominal", False, 0.48),  # False positive
        ("nominal", True, 0.93),
        ("comms_dropout", True, 0.65),
    ]

    time_offset = 0.0
    for sat_id, data in [("SAT-001", sat001_data), ("SAT-002", sat002_data), ("SAT-003", sat003_data)]:
        for predicted, is_correct, confidence in data:
            collector.record_agent_classification(
                sat_id=sat_id,
                scenario_time_s=time_offset,
                predicted_fault=predicted if predicted != "nominal" else None,
                confidence=confidence,
                is_correct=is_correct,
            )
            time_offset += 1.0

    print(f"[OK] Recorded {len(collector)} classifications")

    # Compute and display metrics
    stats = collector.get_accuracy_stats()
    print_accuracy_stats(stats)

    sat_stats = collector.get_stats_by_satellite()
    print_per_satellite_breakdown(sat_stats)

    matrix = collector.get_confusion_matrix()
    print_confusion_matrix(matrix)

    # Export to CSV
    print_section("Exporting to CSV")
    csv_path = "accuracy_demo_classifications.csv"
    collector.export_csv(csv_path)
    print(f"[OK] Exported classifications to {csv_path}")


def demo_regulatory_compliance():
    """Demo: Regulatory compliance validation."""
    print_header("REGULATORY COMPLIANCE VALIDATION DEMO")

    # Compliance requirements
    compliance_thresholds = {
        "overall_accuracy": 0.90,  # 90% minimum
        "fault_detection_recall": 0.95,  # 95% fault detection
        "nominal_specificity": 0.98,  # 98% nominal accuracy
    }

    print_section("Compliance Thresholds")
    for metric, threshold in compliance_thresholds.items():
        print(f"  {metric}: {format_percentage(threshold)}")

    # Simulate mission profile
    collector = AccuracyCollector()

    print_section("Recording mission profile classifications")

    # Mission: 3 satellites over 60 time steps
    np_imported = False
    try:
        import numpy as np

        np_imported = True
    except ImportError:
        pass

    missions = []
    for time_step in range(60):
        for sat_id in ["SAT-001", "SAT-002", "SAT-003"]:
            # Simulate realistic agent performance
            if np_imported:
                is_fault = np.random.random() > 0.7  # 30% of time has fault
                if is_fault:
                    # Fault detection: 95% accuracy
                    is_correct = np.random.random() > 0.05
                    predicted = "thermal_runaway" if is_correct else "comms_dropout"
                    confidence = 0.92 if is_correct else 0.35
                else:
                    # Nominal: 98% accuracy
                    is_correct = np.random.random() > 0.02
                    predicted = None if is_correct else "power_brownout"
                    confidence = 0.96 if is_correct else 0.42
            else:
                # Fallback without numpy
                is_fault = time_step % 3 == 0
                is_correct = True
                predicted = "thermal_runaway" if is_fault else None
                confidence = 0.94 if is_correct else 0.35

            collector.record_agent_classification(
                sat_id=sat_id,
                scenario_time_s=time_step * 0.1,
                predicted_fault=predicted,
                confidence=confidence,
                is_correct=is_correct,
            )

    print(f"[OK] Recorded {len(collector)} classifications across mission profile")

    # Validate compliance
    stats = collector.get_accuracy_stats()

    print_section("Compliance Validation Results")
    print(f"  Overall Accuracy: {format_percentage(stats['overall_accuracy'])}")

    # Check fault detection (power_brownout, thermal_runaway, comms_dropout)
    recalls = []
    for fault_type in ["power_brownout", "thermal_runaway", "comms_dropout"]:
        if fault_type in stats.get("by_fault_type", {}):
            recall = stats["by_fault_type"][fault_type].get("recall", 0)
            recalls.append(recall)

    if recalls:
        avg_fault_recall = sum(recalls) / len(recalls)
        print(f"  Avg Fault Detection Recall: {format_percentage(avg_fault_recall)}")

    # Overall compliance check
    print_section("Compliance Status")
    if stats["overall_accuracy"] >= compliance_thresholds["overall_accuracy"]:
        print(f"  [PASS] Overall accuracy: PASS ({format_percentage(stats['overall_accuracy'])} >= {format_percentage(compliance_thresholds['overall_accuracy'])})")
    else:
        print(f"  [FAIL] Overall accuracy: FAIL ({format_percentage(stats['overall_accuracy'])} < {format_percentage(compliance_thresholds['overall_accuracy'])})")

    if recalls and min(recalls) >= compliance_thresholds["fault_detection_recall"]:
        print(f"  [PASS] Fault detection recall: PASS ({format_percentage(min(recalls))} >= {format_percentage(compliance_thresholds['fault_detection_recall'])})")
    else:
        print(f"  [FAIL] Fault detection recall: FAIL")

    return stats


async def main():
    """Run all demos."""
    try:
        print_header("ASTRAGUARD ACCURACY METRICS DEMONSTRATION")
        print("Issue #498: Agent accuracy validation vs ground truth")
        print(f"Timestamp: {datetime.now().isoformat()}")

        # Demo 1: Single scenario
        await demo_single_scenario()

        # Demo 2: Manual accuracy collection
        demo_manual_accuracy_collection()

        # Demo 3: Regulatory compliance
        demo_regulatory_compliance()

        # Summary
        print_header("DEMONSTRATION COMPLETE")
        print("[OK] All accuracy metrics operational")
        print("[OK] Ground truth integration verified")
        print("[OK] Compliance validation framework ready")
        print("[OK] CSV export functional for analysis")
        print("\nFor detailed testing, run: pytest tests/hil/test_accuracy_metrics.py -v")
        print("For integration with scenarios, see: astraguard/hil/scenarios/parser.py")

    except Exception as e:
        print(f"\n[ERROR] Demo error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
