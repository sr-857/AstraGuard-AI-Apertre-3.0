"""
System Diagnostics Module

Gather low-level system metrics and application health for operational insight.
"""

import os
import sys
import platform
import psutil
import socket
from datetime import datetime
from typing import Dict, Any, List

from core.component_health import get_health_monitor

class SystemDiagnostics:
    """aggregates system metrics and health info."""

    def __init__(self):
        self.health_monitor = get_health_monitor()

    def get_system_info(self) -> Dict[str, Any]:
        """Get static system information."""
        return {
            "os": f"{platform.system()} {platform.release()}",
            "hostname": socket.gethostname(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        }

    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage metrics."""
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu": {
                "total_percent": psutil.cpu_percent(interval=None), # Already waited in percpu
                "per_core": cpu_percent,
                "load_avg": psutil.getloadavg() if hasattr(psutil, "getloadavg") else []
            },
            "memory": {
                "total": mem.total,
                "available": mem.available,
                "percent": mem.percent,
                "used": mem.used
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "percent": swap.percent
            },
            "disk_root": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        }

    def get_network_info(self) -> Dict[str, Any]:
        """Get network I/O statistics."""
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout
        }

    def get_process_info(self) -> Dict[str, Any]:
        """Get info about the current process."""
        p = psutil.Process(os.getpid())
        return {
            "pid": p.pid,
            "name": p.name(),
            "status": p.status(),
            "cpu_percent": p.cpu_percent(interval=None),
            "memory_percent": p.memory_percent(),
            "num_threads": p.num_threads(),
            "open_files": len(p.open_files()),
            "create_time": datetime.fromtimestamp(p.create_time()).isoformat()
        }

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Aggregate all diagnostic information."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": self.get_system_info(),
            "resources": self.get_resource_usage(),
            "network": self.get_network_info(),
            "process": self.get_process_info(),
            "application_health": self.health_monitor.get_system_status()
        }
