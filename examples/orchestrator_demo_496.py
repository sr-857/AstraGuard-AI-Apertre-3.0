"""Demo: Orchestrated parallel test campaigns (Issue #496)."""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from astraguard.hil.scenarios.orchestrator import ScenarioOrchestrator
from astraguard.hil.results.storage import ResultStorage


async def demo_single_campaign():
    """Demo 1: Run campaign with specific scenarios."""
    print("=" * 70)
    print("[DEMO 1] Single Campaign: 2 Scenarios, Parallel=2, Speed=50x")
    print("=" * 70)

    orchestrator = ScenarioOrchestrator()

    # Discover scenarios
    print("\n[DISCOVERY] Scanning for scenarios...")
    discovered = await orchestrator.discover_scenarios()

    if not discovered:
        print("[ERROR] No scenarios found")
        return

    print(f"[OK] Found {len(discovered)} scenarios:")
    for path, scenario in discovered[:2]:
        print(f"  - {scenario.name} ({len(scenario.satellites)} satellites, {scenario.duration_s}s)")

    # Run campaign with first 2 scenarios
    scenario_paths = [path for path, _ in discovered[:2]]
    print(f"\n[CAMPAIGN] Running {len(scenario_paths)} scenarios...")
    print("           (max 2 parallel, 50x speed)")

    results = await orchestrator.run_campaign(
        scenario_paths,
        parallel=2,
        speed=50.0,
        verbose=True,
    )

    # Show results
    print("\n[RESULTS] Campaign completed")
    print("-" * 70)
    passed = sum(1 for r in results.values() if r.get("success"))
    total = len(results)
    print(f"Total: {total} scenarios")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass Rate: {100*passed/total if total > 0 else 0:.0f}%")

    # Show execution times
    print("\n[EXECUTION TIMES]")
    for scenario_name, result in results.items():
        exec_time = result.get("execution_time_s", 0)
        sim_time = result.get("simulated_time_s", 0)
        if sim_time > 0:
            efficiency = sim_time / exec_time
            print(f"  {scenario_name}: {exec_time:.1f}s wall time ({efficiency:.0f}x efficiency)")
        else:
            if result.get("success"):
                print(f"  {scenario_name}: {exec_time:.1f}s wall time")
            else:
                error = result.get("error", "unknown error")
                print(f"  {scenario_name}: FAILED ({error[:40]}...)")


async def demo_full_suite():
    """Demo 2: Run full test suite (all scenarios)."""
    print("\n\n" + "=" * 70)
    print("[DEMO 2] Full Test Suite: All Scenarios, Parallel=3, Speed=100x")
    print("=" * 70)

    orchestrator = ScenarioOrchestrator()

    # Run all scenarios
    print("\n[CAMPAIGN] Running all discovered scenarios...")
    print("           (max 3 parallel, 100x speed)")

    summary = await orchestrator.run_all_scenarios(
        parallel=3,
        speed=100.0,
        verbose=True,
    )

    # Show summary
    print("\n[CAMPAIGN SUMMARY]")
    print("-" * 70)
    print(f"Campaign ID: {summary['campaign_id']}")
    print(f"Total Scenarios: {summary['total_scenarios']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass Rate: {100*summary['pass_rate']:.0f}%")
    print(f"Speed Multiplier: {summary['speed_multiplier']}x")
    print(f"Parallelism: {summary['parallel_limit']}")

    # Show per-scenario status
    if summary.get("results"):
        print("\n[PER-SCENARIO RESULTS]")
        for scenario_name, result in summary["results"].items():
            status = "[PASS]" if result.get("success") else "[FAIL]"
            print(f"  {status} {scenario_name}")


async def demo_result_analysis():
    """Demo 3: Analyze campaign history and statistics."""
    print("\n\n" + "=" * 70)
    print("[DEMO 3] Result Analysis: Campaign History & Statistics")
    print("=" * 70)

    storage = ResultStorage()

    # Get recent campaigns
    print("\n[HISTORY] Recent campaigns:")
    campaigns = storage.get_recent_campaigns(limit=5)

    if campaigns:
        for campaign in campaigns[:3]:  # Show top 3
            print(f"  Campaign {campaign['campaign_id']}: "
                  f"{campaign['passed']}/{campaign['total_scenarios']} passed "
                  f"({100*campaign['pass_rate']:.0f}%)")
    else:
        print("  (No campaigns found)")

    # Get statistics
    print("\n[STATISTICS] Aggregate results:")
    stats = storage.get_result_statistics()
    print(f"  Total campaigns: {stats['total_campaigns']}")
    print(f"  Total scenarios: {stats['total_scenarios']}")
    print(f"  Total passed: {stats['total_passed']}")
    print(f"  Average pass rate: {100*stats['avg_pass_rate']:.0f}%")


async def main():
    """Run all demos."""
    print("\n")
    print("*" * 70)
    print("* AstraGuard-AI HIL Test Orchestration Demo (Issue #496)")
    print("*" * 70)

    try:
        # Demo 1: Single campaign
        await demo_single_campaign()

        # Demo 2: Full suite
        await demo_full_suite()

        # Demo 3: Analysis
        await demo_result_analysis()

        print("\n\n" + "=" * 70)
        print("[SUCCESS] All orchestration demos completed!")
        print("=" * 70)
        print("\nKey features demonstrated:")
        print("  [OK] Scenario auto-discovery from YAML files")
        print("  [OK] Parallel execution with semaphore-based concurrency control")
        print("  [OK] Campaign result aggregation and pass rate calculation")
        print("  [OK] Persistent JSON storage with campaign summaries")
        print("  [OK] Result history and statistical analysis")

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
