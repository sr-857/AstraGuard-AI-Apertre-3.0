#!/usr/bin/env python3
"""
Profiling Runner for AstraGuard AI Backend

Unified wrapper around multiple Python profilers:
- pyinstrument: Statistical profiler with flamegraph-style HTML output
- cProfile + snakeviz: Deterministic profiling with visualization

Usage:
    python tools/benchmarks/run_profile.py --target backend.fallback.manager
    python tools/benchmarks/run_profile.py --profiler cprofile --target backend.main
    python tools/benchmarks/run_profile.py --help
"""

import argparse
import importlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_output_dir() -> Path:
    """Create and return the profiling output directory."""
    output_dir = PROJECT_ROOT / "profiling_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def profile_with_pyinstrument(target_module: str, function: str | None, output_path: Path) -> None:
    """Profile using pyinstrument (statistical profiler)."""
    try:
        from pyinstrument import Profiler
    except ImportError:
        print("ERROR: pyinstrument not installed. Install with: pip install pyinstrument")
        sys.exit(1)

    print(f"Profiling {target_module} with pyinstrument...")
    
    profiler = Profiler()
    
    try:
        module = importlib.import_module(target_module)
    except ImportError as e:
        print(f"ERROR: Could not import module {target_module}: {e}")
        sys.exit(1)

    # If a specific function is provided, profile just that function
    if function:
        if not hasattr(module, function):
            print(f"ERROR: Function '{function}' not found in module {target_module}")
            sys.exit(1)
        
        target_func = getattr(module, function)
        profiler.start()
        try:
            # Handle async functions
            import asyncio
            if asyncio.iscoroutinefunction(target_func):
                asyncio.run(target_func())
            else:
                target_func()
        finally:
            profiler.stop()
    else:
        # Just import and profile module initialization
        profiler.start()
        importlib.reload(module)
        profiler.stop()

    # Save HTML output
    html_output = profiler.output_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)
    
    print(f"Profile saved to: {output_path}")
    print("\nConsole output:")
    print(profiler.output_text(unicode=True, color=True))


def profile_with_cprofile(target_module: str, function: str | None, output_path: Path) -> None:
    """Profile using cProfile (deterministic profiler)."""
    import cProfile
    import pstats
    import io

    print(f"Profiling {target_module} with cProfile...")

    profiler = cProfile.Profile()

    try:
        module = importlib.import_module(target_module)
    except ImportError as e:
        print(f"ERROR: Could not import module {target_module}: {e}")
        sys.exit(1)

    if function:
        if not hasattr(module, function):
            print(f"ERROR: Function '{function}' not found in module {target_module}")
            sys.exit(1)
        
        target_func = getattr(module, function)
        profiler.enable()
        try:
            import asyncio
            if asyncio.iscoroutinefunction(target_func):
                asyncio.run(target_func())
            else:
                target_func()
        finally:
            profiler.disable()
    else:
        profiler.enable()
        importlib.reload(module)
        profiler.disable()

    # Save stats file for snakeviz
    stats_path = output_path.with_suffix(".prof")
    profiler.dump_stats(str(stats_path))
    print(f"cProfile stats saved to: {stats_path}")
    print(f"View with: python -m snakeviz {stats_path}")

    # Also save text summary
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(30)

    text_output = stream.getvalue()
    with open(output_path.with_suffix(".txt"), "w", encoding="utf-8") as f:
        f.write(text_output)

    print("\nTop 30 functions by cumulative time:")
    print(text_output)


def profile_memory(target_module: str, function: str | None, output_path: Path) -> None:
    """Profile memory usage using memory_profiler."""
    try:
        from memory_profiler import memory_usage
    except ImportError:
        print("ERROR: memory_profiler not installed. Install with: pip install memory-profiler")
        sys.exit(1)

    print(f"Profiling memory for {target_module}...")

    try:
        module = importlib.import_module(target_module)
    except ImportError as e:
        print(f"ERROR: Could not import module {target_module}: {e}")
        sys.exit(1)

    def target_func_wrapper():
        if function:
            if not hasattr(module, function):
                print(f"ERROR: Function '{function}' not found in module {target_module}")
                return
            target = getattr(module, function)
            import asyncio
            if asyncio.iscoroutinefunction(target):
                asyncio.run(target())
            else:
                target()
        else:
            importlib.reload(module)

    # Measure memory usage
    mem_usage = memory_usage(target_func_wrapper, interval=0.1, timeout=60)

    # Generate report
    report = f"""Memory Profile Report
=====================
Target: {target_module}{'.' + function if function else ''}
Generated: {datetime.now().isoformat()}

Peak Memory: {max(mem_usage):.2f} MiB
Min Memory: {min(mem_usage):.2f} MiB
Mean Memory: {sum(mem_usage) / len(mem_usage):.2f} MiB
Samples: {len(mem_usage)}
"""

    with open(output_path.with_suffix(".memory.txt"), "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"Memory profile saved to: {output_path.with_suffix('.memory.txt')}")


def main():
    parser = argparse.ArgumentParser(
        description="Profile AstraGuard AI backend modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Profile fallback manager with pyinstrument
    python tools/benchmarks/run_profile.py --target backend.fallback.manager

    # Profile specific function with cProfile
    python tools/benchmarks/run_profile.py --profiler cprofile --target backend.safe_condition_parser --function evaluate

    # Profile memory usage
    python tools/benchmarks/run_profile.py --profiler memory --target backend.cache.in_memory
        """
    )

    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target module to profile (e.g., backend.fallback.manager)"
    )
    parser.add_argument(
        "--function", "-f",
        default=None,
        help="Specific function to profile (optional)"
    )
    parser.add_argument(
        "--profiler", "-p",
        choices=["pyinstrument", "cprofile", "memory"],
        default="pyinstrument",
        help="Profiler to use (default: pyinstrument)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output filename (default: auto-generated based on target)"
    )

    args = parser.parse_args()

    output_dir = setup_output_dir()
    
    # Generate output filename
    if args.output:
        output_path = output_dir / args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = args.target.replace(".", "_")
        suffix = f"_{args.function}" if args.function else ""
        output_path = output_dir / f"{safe_target}{suffix}_{timestamp}.html"

    # Run appropriate profiler
    if args.profiler == "pyinstrument":
        profile_with_pyinstrument(args.target, args.function, output_path)
    elif args.profiler == "cprofile":
        profile_with_cprofile(args.target, args.function, output_path)
    elif args.profiler == "memory":
        profile_memory(args.target, args.function, output_path)


if __name__ == "__main__":
    main()
