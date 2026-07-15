"""
Deadlock Detection for AstraGuard

Detects potential deadlocks in async operations using dependency graph analysis.
Monitors resource acquisition patterns and alerts on circular wait conditions.
"""

import logging
import threading
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any
from datetime import datetime
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class DeadlockStatus(str, Enum):
    """Deadlock detection status"""
    NO_DEADLOCK = "no_deadlock"
    POTENTIAL_DEADLOCK = "potential_deadlock"
    DEADLOCK_DETECTED = "deadlock_detected"


@dataclass
class ResourceDependency:
    """Represents a resource dependency"""
    task_id: str
    resource_id: str
    waiting_for: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "waiting_for": self.waiting_for,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DeadlockReport:
    """Report of deadlock detection results"""
    status: DeadlockStatus
    cycle: List[str] = field(default_factory=list)
    affected_tasks: Set[str] = field(default_factory=set)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "cycle": self.cycle,
            "affected_tasks": list(self.affected_tasks),
            "timestamp": self.timestamp.isoformat()
        }


class DeadlockDetector:
    """
    Detect potential deadlocks using dependency graph analysis.
    
    Features:
    - Track resource acquisition and waiting patterns
    - Detect circular wait conditions (deadlock cycles)
    - Alert on potential deadlocks
    - Thread-safe operation
    """
    
    def __init__(self, check_interval_seconds: float = 5.0):
        """
        Initialize deadlock detector.
        
        Args:
            check_interval_seconds: How often to check for deadlocks
        """
        self.check_interval = check_interval_seconds
        self._dependencies: Dict[str, ResourceDependency] = {}
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info(f"DeadlockDetector initialized with check interval: {check_interval_seconds}s")
    
    def register_dependency(self, task_id: str, resource_id: str, waiting_for: Optional[str] = None):
        """
        Register a resource dependency.
        
        Args:
            task_id: ID of the task acquiring the resource
            resource_id: ID of the resource being acquired
            waiting_for: Optional ID of resource this task is waiting for
        """
        with self._lock:
            dep = ResourceDependency(
                task_id=task_id,
                resource_id=resource_id,
                waiting_for=waiting_for
            )
            self._dependencies[task_id] = dep
            
            logger.debug(
                f"Registered dependency: task={task_id}, resource={resource_id}, "
                f"waiting_for={waiting_for}"
            )
    
    def release_dependency(self, task_id: str):
        """
        Release a resource dependency.
        
        Args:
            task_id: ID of the task releasing the resource
        """
        with self._lock:
            if task_id in self._dependencies:
                del self._dependencies[task_id]
                logger.debug(f"Released dependency for task: {task_id}")
    
    def detect_deadlock(self) -> DeadlockReport:
        """
        Detect deadlocks using cycle detection in dependency graph.
        
        Returns:
            DeadlockReport with detection results
        """
        with self._lock:
            # Build dependency graph: task -> waiting_for_task
            graph: Dict[str, Set[str]] = defaultdict(set)
            resource_owners: Dict[str, str] = {}
            
            # Map resources to their owners
            for task_id, dep in self._dependencies.items():
                if dep.waiting_for is None:
                    # Task owns the resource
                    resource_owners[dep.resource_id] = task_id
            
            # Build wait-for graph
            for task_id, dep in self._dependencies.items():
                if dep.waiting_for:
                    # Task is waiting for a resource
                    owner = resource_owners.get(dep.waiting_for)
                    if owner:
                        graph[task_id].add(owner)
            
            # Detect cycles using DFS
            cycle = self._find_cycle(graph)
            
            if cycle:
                logger.warning(f"Deadlock detected! Cycle: {' -> '.join(cycle)}")
                return DeadlockReport(
                    status=DeadlockStatus.DEADLOCK_DETECTED,
                    cycle=cycle,
                    affected_tasks=set(cycle)
                )
            
            return DeadlockReport(status=DeadlockStatus.NO_DEADLOCK)
    
    def _find_cycle(self, graph: Dict[str, Set[str]]) -> List[str]:
        """
        Find a cycle in the dependency graph using DFS.
        
        Args:
            graph: Adjacency list representation of dependency graph
            
        Returns:
            List of task IDs forming a cycle, or empty list if no cycle
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
            
            path.pop()
            rec_stack.remove(node)
            return None
        
        for node in graph:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result
        
        return []
    
    def get_dependencies(self) -> List[Dict[str, Any]]:
        """
        Get all current dependencies.
        
        Returns:
            List of dependency dictionaries
        """
        with self._lock:
            return [dep.to_dict() for dep in self._dependencies.values()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get deadlock detection statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total_deps = len(self._dependencies)
            waiting_deps = sum(1 for dep in self._dependencies.values() if dep.waiting_for)
            
            return {
                "total_dependencies": total_deps,
                "waiting_dependencies": waiting_deps,
                "active_dependencies": total_deps - waiting_deps,
                "monitoring_active": self._monitoring,
                "check_interval_seconds": self.check_interval
            }
    
    async def start_monitoring(self):
        """Start continuous deadlock monitoring."""
        if self._monitoring:
            logger.warning("Deadlock monitoring already active")
            return
        
        self._monitoring = True
        logger.info("Started deadlock monitoring")
        
        while self._monitoring:
            try:
                report = self.detect_deadlock()
                if report.status == DeadlockStatus.DEADLOCK_DETECTED:
                    logger.error(
                        f"Deadlock detected! Affected tasks: {report.affected_tasks}, "
                        f"Cycle: {' -> '.join(report.cycle)}"
                    )
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in deadlock monitoring: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop continuous deadlock monitoring."""
        self._monitoring = False
        logger.info("Stopped deadlock monitoring")


# Global singleton instance
_deadlock_detector: Optional[DeadlockDetector] = None
_detector_lock = threading.Lock()


def get_deadlock_detector() -> DeadlockDetector:
    """
    Get global deadlock detector singleton.
    
    Returns:
        DeadlockDetector instance
    """
    global _deadlock_detector
    
    if _deadlock_detector is None:
        with _detector_lock:
            if _deadlock_detector is None:
                _deadlock_detector = DeadlockDetector()
    
    return _deadlock_detector
