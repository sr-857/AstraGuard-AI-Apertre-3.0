"""
Anomaly Injection Framework for E2E Recovery Testing
======================================================

Simulates real-world satellite anomalies:
- Battery faults (low power → safe_mode cascade)
- Attitude drift (coverage loss → safety blocks)
- Thermal stress (throttling → performance degradation)
- Memory pressure (OOM triggers → state compression)
- Comm faults (loss of link → isolation → quorum loss)

Each anomaly flows through complete decision pipeline (#397-413).
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import docker
from datetime import datetime

if TYPE_CHECKING:
    from docker.client import DockerClient


class AnomalySeverity(Enum):
    """Anomaly severity levels matching real-world impact."""
    LOW = 0.3        # <80% capacity, no mode change
    MEDIUM = 0.6     # 40-80% capacity, degraded mode
    HIGH = 0.8       # <40% capacity, safe_mode cascade
    CRITICAL = 0.95  # <10% capacity, emergency recovery


@dataclass
class AnomalyInjectionRequest:
    """Anomaly injection specification."""
    anomaly_type: str
    agent_id: str
    severity: float
    duration_seconds: Optional[float] = None
    cascade_enabled: bool = True
    inject_timestamp: float = 0.0
    injected: bool = False


@dataclass
class AnomalyEvent:
    """Anomaly event recorded in pipeline."""
    timestamp: float
    anomaly_type: str
    agent_id: str
    severity: float
    detection_latency_seconds: float
    decision_latency_seconds: float
    execution_latency_seconds: float
    total_pipeline_latency_seconds: float
    affected_agents: int
    safe_mode_triggered: bool
    recovery_time_seconds: Optional[float] = None


class AnomalyInjector:
    """
    Injects simulated satellite anomalies into constellation.
    
    Coordinates with:
    - #401: Health monitoring (detects anomaly)
    - #405: Leadership election (handles failures)
    - #406: Consensus protocol (quorum impact)
    - #408: Role propagation (duty reassignment)
    - #409: Role assignment (coverage changes)
    - #412: ActionScope (tracks impact)
    - #413: Safety simulator (blocks unsafe recovery)
    """
    
    def __init__(self, docker_client: "DockerClient", network_name: str = "isl-net"):
        """
        Initialize anomaly injector.
        
        Args:
            docker_client: Docker API client for container manipulation
            network_name: Docker network name (ISL communication network)
        """
        self.docker_client = docker_client
        self.network_name = network_name
        self.active_anomalies: Dict[str, AnomalyInjectionRequest] = {}
        self.anomaly_timeline: List[AnomalyEvent] = []
        self._inject_start_time: Dict[str, float] = {}
    
    async def inject_battery_fault(
        self,
        agent_id: str,
        severity: float = 0.8,
        duration_seconds: Optional[float] = None
    ) -> AnomalyInjectionRequest:
        """
        Inject battery fault (low power condition).
        
        Simulates battery draining to trigger safe_mode cascade:
        - severity 0.3: Battery >80%, capacity reduction only
        - severity 0.6: Battery 40-80%, degraded_mode possible
        - severity 0.8: Battery <40%, safe_mode triggered
        - severity 0.95: Battery <10%, emergency recovery
        
        Flow:
        1. #401 health monitor detects low battery
        2. #405 leader broadcasts alert
        3. #406 consensus updates power state
        4. #408 propagates reduced duty cycle
        5. #409 reassigns roles to higher-power agents
        6. #412 ActionScope tracks power impact
        7. #413 Safety sim validates safe mode is allowed
        8. RECOVERY: Agent returns to full power
        
        Args:
            agent_id: Agent to affect (e.g., "SAT-001-A")
            severity: 0.0-1.0 power loss (1.0 = completely dead)
            duration_seconds: How long to maintain fault (None = manual recovery)
            
        Returns:
            AnomalyInjectionRequest with injection metadata
        """
        request = AnomalyInjectionRequest(
            anomaly_type="battery_fault",
            agent_id=agent_id,
            severity=severity,
            duration_seconds=duration_seconds,
            cascade_enabled=True,
            inject_timestamp=time.time(),
        )
        
        # Extract container from agent_id (SAT-001-A -> astra-sat-001-a)
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Simulate battery state via health check hook
            # Container responds with reduced capacity on health check
            battery_remaining = 100.0 * (1.0 - severity)
            env_update = {
                "SIMULATED_BATTERY_PCT": str(int(battery_remaining)),
                "POWER_STATE": "safe_mode" if severity >= 0.8 else "degraded",
            }
            
            # Update via environment variable simulation
            # (In real system: actual power management integration)
            await self._exec_in_container(
                container,
                f"export SIMULATED_BATTERY_PCT={battery_remaining}; "
                f"export POWER_STATE={'safe_mode' if severity >= 0.8 else 'degraded'}"
            )
            
            self.active_anomalies[agent_id] = request
            self._inject_start_time[agent_id] = time.time()
            request.injected = True
            
            # Schedule auto-recovery if duration specified
            if duration_seconds is not None:
                asyncio.create_task(
                    self._recover_after_delay(agent_id, duration_seconds)
                )
            
            return request
            
        except Exception as e:
            raise RuntimeError(f"Failed to inject battery fault on {agent_id}: {e}")
    
    async def inject_attitude_fault(
        self,
        agent_id: str,
        drift_degrees: float = 10.0,
        duration_seconds: Optional[float] = None
    ) -> AnomalyInjectionRequest:
        """
        Inject attitude drift (loss of satellite orientation).
        
        Simulates attitude error causing:
        - Coverage loss (antenna miss)
        - Safety constraints blocking recovery (#413)
        - Role reassignment to cover gap
        
        Flow:
        1. #401 detects attitude error >threshold
        2. #405 leader broadcasts coverage gap alert
        3. #413 Safety sim BLOCKS any recovery attempts (safety first)
        4. #408 propagates new coverage map
        5. #409 reassigns roles (agent goes to monitor-only)
        6. RECOVERY: Attitude corrected, normal operations resume
        
        Args:
            agent_id: Agent to affect
            drift_degrees: Attitude error in degrees (10° = lose ISL link)
            duration_seconds: How long to maintain fault
            
        Returns:
            AnomalyInjectionRequest with injection metadata
        """
        request = AnomalyInjectionRequest(
            anomaly_type="attitude_fault",
            agent_id=agent_id,
            severity=min(drift_degrees / 180.0, 0.95),
            duration_seconds=duration_seconds,
            cascade_enabled=True,
            inject_timestamp=time.time(),
        )
        
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Simulate attitude state
            await self._exec_in_container(
                container,
                f"export SIMULATED_ATTITUDE_ERROR_DEG={drift_degrees}; "
                f"export COVERAGE_LOSS=true"
            )
            
            self.active_anomalies[agent_id] = request
            self._inject_start_time[agent_id] = time.time()
            request.injected = True
            
            if duration_seconds is not None:
                asyncio.create_task(
                    self._recover_after_delay(agent_id, duration_seconds)
                )
            
            return request
            
        except Exception as e:
            raise RuntimeError(f"Failed to inject attitude fault on {agent_id}: {e}")
    
    async def inject_thermal_stress(
        self,
        agent_id: str,
        severity: float = 0.7,
        duration_seconds: Optional[float] = None
    ) -> AnomalyInjectionRequest:
        """
        Inject thermal stress (CPU throttling).
        
        Simulates temperature rise causing:
        - Reduced CPU frequency (slower decision making)
        - Increased decision latency
        - Potential timeout cascades
        
        Flow:
        1. #401 detects thermal stress
        2. #407 Policy applies throttling policy
        3. #411 Decision latency increases
        4. #406 Consensus slows down
        5. #408 Propagation slower
        6. RECOVERY: Cooling, return to normal
        
        Args:
            agent_id: Agent to affect
            severity: 0.0-1.0 thermal stress (1.0 = critical temp)
            duration_seconds: How long to maintain fault
            
        Returns:
            AnomalyInjectionRequest with injection metadata
        """
        request = AnomalyInjectionRequest(
            anomaly_type="thermal_stress",
            agent_id=agent_id,
            severity=severity,
            duration_seconds=duration_seconds,
            cascade_enabled=True,
            inject_timestamp=time.time(),
        )
        
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Reduce container CPU allocation to simulate throttling
            cpu_quota = int(50000 * (1.0 - severity * 0.6))  # 50000 = normal
            
            # Update container CPU limits
            container.update(cpu_quota=cpu_quota)
            
            self.active_anomalies[agent_id] = request
            self._inject_start_time[agent_id] = time.time()
            request.injected = True
            
            if duration_seconds is not None:
                asyncio.create_task(
                    self._recover_after_delay(agent_id, duration_seconds)
                )
            
            return request
            
        except Exception as e:
            raise RuntimeError(f"Failed to inject thermal stress on {agent_id}: {e}")
    
    async def inject_memory_pressure(
        self,
        agent_id: str,
        severity: float = 0.7,
        duration_seconds: Optional[float] = None
    ) -> AnomalyInjectionRequest:
        """
        Inject memory pressure (state compression cascade).
        
        Simulates memory constraint causing:
        - State compression (#410 memory efficiency)
        - Decision queue pressure (#411)
        - Potential packet loss on retransmit
        
        Flow:
        1. #401 detects memory pressure
        2. #410 Memory efficiency kicks in (compression)
        3. #411 Decision queue backs up
        4. #406 Consensus latency increases
        5. RECOVERY: Memory freed, normal state
        
        Args:
            agent_id: Agent to affect
            severity: 0.0-1.0 memory usage (1.0 = OOM)
            duration_seconds: How long to maintain fault
            
        Returns:
            AnomalyInjectionRequest with injection metadata
        """
        request = AnomalyInjectionRequest(
            anomaly_type="memory_pressure",
            agent_id=agent_id,
            severity=severity,
            duration_seconds=duration_seconds,
            cascade_enabled=True,
            inject_timestamp=time.time(),
        )
        
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Reduce memory limit to force pressure
            memory_bytes = int(512e6 * (1.0 - severity * 0.5))  # 512MB normal
            
            # Update container memory limits
            container.update(mem_limit=memory_bytes)
            
            self.active_anomalies[agent_id] = request
            self._inject_start_time[agent_id] = time.time()
            request.injected = True
            
            if duration_seconds is not None:
                asyncio.create_task(
                    self._recover_after_delay(agent_id, duration_seconds)
                )
            
            return request
            
        except Exception as e:
            raise RuntimeError(f"Failed to inject memory pressure on {agent_id}: {e}")
    
    async def inject_comm_fault(
        self,
        agent_id: str,
        link_loss_percent: int = 50,
        duration_seconds: Optional[float] = None
    ) -> AnomalyInjectionRequest:
        """
        Inject communication fault (link degradation).
        
        Simulates ISL packet loss causing:
        - Message delivery degradation (#403)
        - Consensus latency increase (#406)
        - Potential quorum loss if 50%+ (#406)
        
        Flow:
        1. Packet loss injected via tc (traffic control)
        2. #403 Reliable delivery triggers retries
        3. #406 Consensus latency increases
        4. #408 Propagation slower
        5. If severe enough: quorum timeout
        6. RECOVERY: Link restored, normal ops
        
        Args:
            agent_id: Agent to affect (loss on its links)
            link_loss_percent: 0-100% packet loss
            duration_seconds: How long to maintain fault
            
        Returns:
            AnomalyInjectionRequest with injection metadata
        """
        request = AnomalyInjectionRequest(
            anomaly_type="comm_fault",
            agent_id=agent_id,
            severity=link_loss_percent / 100.0,
            duration_seconds=duration_seconds,
            cascade_enabled=True,
            inject_timestamp=time.time(),
        )
        
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Inject packet loss via tc
            await self._exec_in_container(
                container,
                f"tc qdisc add dev eth0 root netem loss {link_loss_percent}%"
            )
            
            self.active_anomalies[agent_id] = request
            self._inject_start_time[agent_id] = time.time()
            request.injected = True
            
            if duration_seconds is not None:
                asyncio.create_task(
                    self._recover_after_delay(agent_id, duration_seconds)
                )
            
            return request
            
        except Exception as e:
            raise RuntimeError(f"Failed to inject comm fault on {agent_id}: {e}")
    
    async def recover_anomaly(self, agent_id: str) -> None:
        """
        Recover from anomaly (manual recovery).
        
        Removes anomaly state and allows swarm recovery path.
        """
        if agent_id not in self.active_anomalies:
            return
        
        request = self.active_anomalies[agent_id]
        container_name = self._agent_to_container(agent_id)
        
        try:
            container = self.docker_client.containers.get(container_name)
            
            # Clear anomaly state based on type
            if request.anomaly_type == "battery_fault":
                await self._exec_in_container(
                    container,
                    "export SIMULATED_BATTERY_PCT=100; export POWER_STATE=normal"
                )
            elif request.anomaly_type == "attitude_fault":
                await self._exec_in_container(
                    container,
                    "export SIMULATED_ATTITUDE_ERROR_DEG=0; export COVERAGE_LOSS=false"
                )
            elif request.anomaly_type == "thermal_stress":
                # Restore CPU quota
                container.update(cpu_quota=50000)
            elif request.anomaly_type == "memory_pressure":
                # Restore memory limit
                container.update(mem_limit=512e6)
            elif request.anomaly_type == "comm_fault":
                # Remove packet loss rules
                await self._exec_in_container(
                    container,
                    "tc qdisc del dev eth0 root"
                )
            
            if agent_id in self._inject_start_time:
                recovery_time = time.time() - self._inject_start_time[agent_id]
                del self._inject_start_time[agent_id]
            else:
                recovery_time = None
            
            del self.active_anomalies[agent_id]
            
        except Exception as e:
            raise RuntimeError(f"Failed to recover anomaly on {agent_id}: {e}")
    
    async def recover_all(self) -> None:
        """Recover all active anomalies."""
        for agent_id in list(self.active_anomalies.keys()):
            await self.recover_anomaly(agent_id)
    
    def get_active_anomalies(self) -> Dict[str, AnomalyInjectionRequest]:
        """Get currently active anomalies."""
        return self.active_anomalies.copy()
    
    def get_anomaly_timeline(self) -> List[AnomalyEvent]:
        """Get recorded anomaly events from this session."""
        return self.anomaly_timeline.copy()
    
    async def _recover_after_delay(self, agent_id: str, delay_seconds: float) -> None:
        """Schedule recovery after specified delay."""
        await asyncio.sleep(delay_seconds)
        await self.recover_anomaly(agent_id)
    
    async def _exec_in_container(self, container, command: str) -> str:
        """Execute command inside container."""
        result = container.exec_run(f"sh -c '{command}'")
        if result.exit_code != 0:
            raise RuntimeError(f"Container command failed: {result.output}")
        return result.output.decode() if result.output else ""
    
    @staticmethod
    def _agent_to_container(agent_id: str) -> str:
        """Convert agent ID to container name."""
        # SAT-001-A -> astra-sat-001-a
        return f"astra-{agent_id.lower().replace('_', '-')}"
