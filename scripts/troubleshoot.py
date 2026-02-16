#!/usr/bin/env python3
"""
AstraGuard AI — Troubleshooting Script

Helps developers quickly diagnose common setup and runtime issues.
Checks Python version, dependencies, environment files, port availability,
Redis connectivity, Docker availability, directory structure, and more.

Usage:
    python scripts/troubleshoot.py            # Run all checks
    python scripts/troubleshoot.py --fix      # Run all checks and offer auto-fixes
    python scripts/troubleshoot.py --check env # Run only the env check
"""

import argparse
import importlib
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this script: scripts/ -> repo root)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Key paths relative to the project root
REQUIREMENTS_FILE = PROJECT_ROOT / "src" / "config" / "requirements.txt"
ENV_EXAMPLE = PROJECT_ROOT / "src" / "config" / ".env.example"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_LOCAL = PROJECT_ROOT / ".env.local"

# Required directories (relative to project root)
REQUIRED_DIRS = [
    "src",
    "src/anomaly",
    "src/api",
    "src/backend",
    "src/config",
    "src/core",
    "scripts",
    "tests",
    "docs",
    "ui",
    "infra",
]

# Ports that AstraGuard services commonly use
SERVICE_PORTS: Dict[int, str] = {
    8000: "FastAPI (default)",
    8002: "FastAPI (start-app.js)",
    3000: "Next.js frontend",
    8501: "Streamlit dashboard",
    6379: "Redis",
}

# Core Python packages that must be importable for the system to run
CORE_PACKAGES = [
    "numpy",
    "pandas",
    "fastapi",
    "uvicorn",
    "pydantic",
    "loguru",
    "redis",
    "prometheus_client",
    "psutil",
]


# ===== Utility helpers =====================================================

def _header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}")


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _info(msg: str) -> None:
    print(f"  ℹ️  {msg}")


def _cmd_available(cmd: str) -> bool:
    """Return True if *cmd* is on the PATH."""
    return shutil.which(cmd) is not None


def _run(cmd: List[str], timeout: int = 10) -> Tuple[bool, str]:
    """Run a command, return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {timeout}s"
    except (OSError, ValueError) as exc:
        return False, str(exc)


# ===== Individual checks ===================================================

def check_python() -> bool:
    """Verify Python >= 3.9."""
    _header("Python Version")
    v = sys.version_info
    if v.major == 3 and v.minor >= 9:
        _ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    _fail(f"Python {v.major}.{v.minor}.{v.micro} — requires 3.9+")
    _info("Install Python 3.9+ from https://python.org")
    return False


def check_node() -> bool:
    """Check for Node.js and npm."""
    _header("Node.js / npm")
    ok = True

    if _cmd_available("node"):
        success, out = _run(["node", "--version"])
        if success:
            _ok(f"Node.js {out}")
        else:
            _warn(f"node found but version check failed: {out}")
            ok = False
    else:
        _warn("Node.js not found (needed for frontend)")
        _info("Install from https://nodejs.org")
        ok = False

    if _cmd_available("npm"):
        success, out = _run(["npm", "--version"])
        if success:
            _ok(f"npm {out}")
        else:
            _warn(f"npm found but version check failed: {out}")
            ok = False
    else:
        _warn("npm not found (needed for frontend build)")
        ok = False

    return ok


def check_dependencies() -> bool:
    """Verify core Python packages are importable."""
    _header("Python Dependencies")
    missing: List[str] = []
    for pkg in CORE_PACKAGES:
        try:
            importlib.import_module(pkg)
            _ok(pkg)
        except ImportError:
            _fail(f"{pkg} — not installed")
            missing.append(pkg)

    if missing:
        _info(f"Install missing packages:")
        _info(f"  pip install {' '.join(missing)}")
        _info(f"Or install all requirements:")
        _info(f"  pip install -r {REQUIREMENTS_FILE.relative_to(PROJECT_ROOT)}")
        return False
    return True


def check_env(*, auto_fix: bool = False) -> bool:
    """Check that an environment file exists."""
    _header("Environment Configuration")
    ok = True

    if ENV_FILE.exists():
        _ok(f".env file found at {ENV_FILE.relative_to(PROJECT_ROOT)}")
    elif ENV_LOCAL.exists():
        _ok(f".env.local file found at {ENV_LOCAL.relative_to(PROJECT_ROOT)}")
    else:
        _warn("No .env or .env.local file found at project root")
        if ENV_EXAMPLE.exists():
            if auto_fix:
                shutil.copy2(ENV_EXAMPLE, ENV_FILE)
                _ok(f"Created .env from {ENV_EXAMPLE.relative_to(PROJECT_ROOT)}")
            else:
                _info(
                    f"Copy the example:  cp {ENV_EXAMPLE.relative_to(PROJECT_ROOT)} .env"
                )
                ok = False
        else:
            _info("No .env.example found either — check project setup docs")
            ok = False

    # Validate key variables if a file exists
    env_path = ENV_FILE if ENV_FILE.exists() else (ENV_LOCAL if ENV_LOCAL.exists() else None)
    if env_path:
        content = env_path.read_text()
        for var in ("REDIS_HOST", "REDIS_PORT", "LOG_LEVEL"):
            if var in content:
                _ok(f"{var} is defined")
            else:
                _warn(f"{var} is not defined in {env_path.name}")
                ok = False

    return ok


def check_ports() -> bool:
    """Check if common service ports are available (not already in use)."""
    _header("Port Availability")
    ok = True
    for port, label in SERVICE_PORTS.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", port))
                if result == 0:
                    # Port is in use — something is already listening
                    _warn(f"Port {port} ({label}) is already in use")
                    ok = False
                else:
                    _ok(f"Port {port} ({label}) is available")
        except OSError:
            _ok(f"Port {port} ({label}) is available")
    return ok


def check_redis() -> bool:
    """Try to connect to Redis."""
    _header("Redis Connectivity")
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((host, port))
        _ok(f"Redis is reachable at {host}:{port}")
        return True
    except (ConnectionRefusedError, OSError):
        _warn(f"Cannot reach Redis at {host}:{port}")
        _info("Redis is optional for local dev, but required for production")
        _info("Start Redis:  redis-server  (or use Docker)")
        return False


def check_docker() -> bool:
    """Check Docker and Docker Compose availability."""
    _header("Docker")
    ok = True

    if _cmd_available("docker"):
        success, out = _run(["docker", "--version"])
        if success:
            _ok(f"Docker: {out}")
        else:
            _warn(f"docker found but: {out}")
            ok = False

        # Check daemon is running
        success, out = _run(["docker", "info"], timeout=5)
        if success:
            _ok("Docker daemon is running")
        else:
            _warn("Docker daemon is not running or not accessible")
            _info("Start Docker Desktop or run: sudo systemctl start docker")
            ok = False
    else:
        _warn("Docker not found (optional, but needed for containerized dev)")
        _info("Install from https://docs.docker.com/get-docker/")
        ok = False

    # Docker Compose (v2 plugin or standalone)
    compose_found = False
    for cmd in (["docker", "compose", "version"], ["docker-compose", "--version"]):
        success, out = _run(cmd)
        if success:
            _ok(f"Docker Compose: {out}")
            compose_found = True
            break
    if not compose_found:
        _warn("Docker Compose not found")
        ok = False

    return ok


def check_dirs() -> bool:
    """Verify essential project directories exist."""
    _header("Directory Structure")
    ok = True
    for d in REQUIRED_DIRS:
        full = PROJECT_ROOT / d
        if full.is_dir():
            _ok(f"{d}/")
        else:
            _fail(f"{d}/ — missing")
            ok = False
    return ok


def check_disk_and_memory() -> bool:
    """Basic system resource check."""
    _header("System Resources")
    ok = True

    try:
        import psutil

        # Disk
        disk = psutil.disk_usage(str(PROJECT_ROOT))
        free_gb = disk.free / (1024**3)
        if free_gb < 1.0:
            _warn(f"Low disk space: {free_gb:.1f} GB free")
            ok = False
        else:
            _ok(f"Disk space: {free_gb:.1f} GB free")

        # Memory
        mem = psutil.virtual_memory()
        avail_gb = mem.available / (1024**3)
        if avail_gb < 0.5:
            _warn(f"Low available memory: {avail_gb:.1f} GB")
            ok = False
        else:
            _ok(f"Available memory: {avail_gb:.1f} GB")
    except ImportError:
        _warn("psutil not installed — skipping resource checks")
        _info("Install it:  pip install psutil")
        ok = False

    return ok


def check_config_files() -> bool:
    """Check that key configuration files exist."""
    _header("Configuration Files")
    ok = True
    configs = {
        "src/config/requirements.txt": "Python dependencies",
        "pyproject.toml": "Project metadata / tool config",
        "package.json": "Node.js project config",
    }
    for path, label in configs.items():
        full = PROJECT_ROOT / path
        if full.exists():
            _ok(f"{path} ({label})")
        else:
            _warn(f"{path} ({label}) — not found")
            ok = False
    return ok


def check_permissions() -> bool:
    """Verify the user can write to key directories."""
    _header("Write Permissions")
    ok = True
    for d in ("src", "scripts", "tests"):
        full = PROJECT_ROOT / d
        if full.is_dir() and os.access(full, os.W_OK):
            _ok(f"{d}/ is writable")
        elif full.is_dir():
            _fail(f"{d}/ is NOT writable")
            ok = False
    return ok


# ===== Runner ==============================================================

# Registry of all available checks
ALL_CHECKS = {
    "python": check_python,
    "node": check_node,
    "deps": check_dependencies,
    "env": None,  # special-cased for --fix
    "ports": check_ports,
    "redis": check_redis,
    "docker": check_docker,
    "dirs": check_dirs,
    "resources": check_disk_and_memory,
    "config": check_config_files,
    "permissions": check_permissions,
}


def run_all(*, auto_fix: bool = False, only: Optional[str] = None) -> bool:
    """Execute checks and print a summary. Returns True if all pass."""
    print()
    print("🛰️  AstraGuard AI — Troubleshooter")
    print(f"   Project root : {PROJECT_ROOT}")
    print(f"   Platform     : {platform.system()} {platform.release()}")
    print(f"   Python       : {sys.executable}")

    results: Dict[str, bool] = {}

    checks_to_run = {only: ALL_CHECKS[only]} if only and only in ALL_CHECKS else ALL_CHECKS

    for name, fn in checks_to_run.items():
        if name == "env":
            results[name] = check_env(auto_fix=auto_fix)
        else:
            results[name] = fn()

    # Summary
    _header("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")

    print()
    if passed == total:
        print(f"  🎉 All {total} checks passed! Your environment looks good.")
    else:
        failed = total - passed
        print(f"  {passed}/{total} checks passed, {failed} need attention.")
        print("  Re-run with --fix to auto-fix what can be fixed.")

    return passed == total


# ===== CLI =================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AstraGuard AI troubleshooting utility",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt automatic fixes (e.g. copy .env.example → .env)",
    )
    parser.add_argument(
        "--check",
        choices=list(ALL_CHECKS.keys()),
        default=None,
        help="Run only a specific check",
    )
    args = parser.parse_args()

    all_ok = run_all(auto_fix=args.fix, only=args.check)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
