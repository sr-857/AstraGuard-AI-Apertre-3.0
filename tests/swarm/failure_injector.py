"""
Failure Injection Framework - Chaos Engineering for Swarm Simulator

Issue #414: Test failure scenarios to validate swarm robustness
Injects various failure modes to stress-test complete pipeline (#397-413)

Failure Categories:
1. Agent failures (crash, hang, anomaly)
2. Network failures (partition, latency, loss)
3. Infrastructure failures (bus down, registry down)
4. Distributed failures (cascading, correlated)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Callable, Dict, Any, TYPE_CHECKING
from enum import Enum
import subprocess
import docker

if TYPE_CHECKING:
    from docker.client import DockerClient

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures to inject."""
    # Agent failures
    AGENT_CRASH = "agent_crash"
    AGENT_HANG = "agent_hang"
    AGENT_MEMORY_LEAK = "agent_memory_leak"
    AGENT_CPU_SPIKE = "agent_cpu_spike"
    
    # Network failures
    NETWORK_PARTITION = "network_partition"
    NETWORK_LATENCY = "network_latency"
    NETWORK_LOSS = "network_loss"
    NETWORK_CORRUPTION = "network_corruption"
    
    # Infrastructure failures
    BUS_DOWN = "bus_down"
    REGISTRY_DOWN = "registry_down"
    PROMETHEUS_DOWN = "prometheus_down"
    
    # Distributed failures
    CASCADING_FAILURE = "cascading_failure"
    CORRELATED_ANOMALY = "correlated_anomaly"


@dataclass
class FailureConfig:
    """Configuration for failure injection."""
    failure_type: FailureType
    target_agents: List[str]  # e.g., ["SAT-001-A", "SAT-002-A"]
    duration_seconds: Optional[int] = None  # None = permanent until recovery
    intensity: float = 1.0  # 0.0-1.0, affects severity
    delay_before_injection_ms: int = 0
    recovery_method: Optional[str] = None  # "restart", "heal", "manual"
    expected_impact: Optional[str] = None  # Description of expected behavior


class FailureInjector:
    """Injects failures into running swarm."""
    
    def __init__(self, docker_client: Optional["DockerClient"] = None):
        """Initialize failure injector."""
        self.docker = docker_client or docker.from_env()
        self.active_failures: Dict[str, FailureConfig] = {}
        self.recovery_tasks: Dict[str, asyncio.Task] = {}
    
    async def inject_agent_crash(self, agent_id: str, delay_ms: int = 0) -> FailureConfig:
        """
        Inject agent crash (SIGKILL container).
        
        Agent dies immediately and is marked dead.
        Should trigger:
        - Health broadcast detects missing heartbeat
        - Leader election if leader crashes
        - Role reassignment if follower crashes
        """
        config = FailureConfig(
            failure_type=FailureType.AGENT_CRASH,
            target_agents=[agent_id],
            delay_before_injection_ms=delay_ms,
            recovery_method="restart",
            expected_impact="Agent marked dead, quorum may be affected"
        )
        
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(f"INJECTING: Agent crash on {agent_id}")
            container.kill()
            self.active_failures[agent_id] = config
        except Exception as e:
            logger.error(f"Failed to crash agent {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_agent_hang(
        self,
        agent_id: str,
        duration_seconds: int,
        delay_ms: int = 0
    ) -> FailureConfig:
        """
        Inject agent hang (SIGSTOP process).
        
        Agent stops responding but container stays alive.
        Health check will timeout, marking agent unhealthy.
        Different from crash - network connections still exist but no heartbeats.
        """
        config = FailureConfig(
            failure_type=FailureType.AGENT_HANG,
            target_agents=[agent_id],
            duration_seconds=duration_seconds,
            delay_before_injection_ms=delay_ms,
            recovery_method="heal",
            expected_impact="Agent unresponsive, health checks fail, triggers recovery"
        )
        
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(f"INJECTING: Agent hang on {agent_id} for {duration_seconds}s")
            
            # Send SIGSTOP to freeze process
            container.kill(signal="SIGSTOP")
            self.active_failures[agent_id] = config
            
            # Schedule recovery
            if duration_seconds:
                task = asyncio.create_task(
                    self._recover_hang(agent_id, duration_seconds)
                )
                self.recovery_tasks[agent_id] = task
        except Exception as e:
            logger.error(f"Failed to hang agent {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_memory_leak(
        self,
        agent_id: str,
        leak_rate_mb_per_sec: float = 10.0,
        duration_seconds: Optional[int] = None
    ) -> FailureConfig:
        """
        Inject memory leak anomaly.
        
        Consumes memory at specified rate to simulate compression pool overflow.
        Should trigger:
        - Memory pool usage > 80% → health degrades
        - Memory pool usage > 90% → health critical
        - Anomaly detected in health broadcast
        - Triggers role reassignment to BACKUP
        """
        config = FailureConfig(
            failure_type=FailureType.AGENT_MEMORY_LEAK,
            target_agents=[agent_id],
            duration_seconds=duration_seconds,
            intensity=leak_rate_mb_per_sec / 50.0,  # Normalize to 0-1
            recovery_method="restart",
            expected_impact="Memory grows, health decreases, triggers role reassignment"
        )
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(
                f"INJECTING: Memory leak on {agent_id} "
                f"({leak_rate_mb_per_sec}MB/s for {duration_seconds}s)"
            )
            
            # Start memory leak process in container
            cmd = f"python3 -c 'import time; "
            cmd += f"data = []; "
            cmd += f"[data.append(bytearray(1024*1024)) for _ in range({int(leak_rate_mb_per_sec)})] "
            cmd += f"if True: time.sleep({duration_seconds or 3600})'"
            
            container.exec_run(cmd, detach=True)
            self.active_failures[agent_id] = config
            
            # Schedule cleanup if duration specified
            if duration_seconds:
                task = asyncio.create_task(
                    self._recover_memory_leak(agent_id, duration_seconds)
                )
                self.recovery_tasks[agent_id] = task
        except Exception as e:
            logger.error(f"Failed to inject memory leak on {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_cpu_spike(
        self,
        agent_id: str,
        duration_seconds: int,
        cpu_percent: float = 80.0
    ) -> FailureConfig:
        """
        Inject CPU spike (busy loop).
        
        Consumes CPU to simulate decision loop overload.
        Should trigger:
        - Increased decision latency
        - Potential consensus timeouts
        - Health degradation if latency critical
        """
        config = FailureConfig(
            failure_type=FailureType.AGENT_CPU_SPIKE,
            target_agents=[agent_id],
            duration_seconds=duration_seconds,
            intensity=cpu_percent / 100.0,
            recovery_method="heal",
            expected_impact="CPU busy, decision latency increases, may trigger timeouts"
        )
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(f"INJECTING: CPU spike on {agent_id} for {duration_seconds}s")
            
            # Start CPU burn process
            cmd = f"python3 -c 'import time; "
            cmd += f"start=time.time(); "
            cmd += f"[_ for _ in range(10**8) if time.time()-start < {duration_seconds}]'"
            
            container.exec_run(cmd, detach=True)
            self.active_failures[agent_id] = config
        except Exception as e:
            logger.error(f"Failed to inject CPU spike on {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_network_partition(
        self,
        isolated_agents: List[str],
        remaining_agents: List[str],
        duration_seconds: Optional[int] = None
    ) -> FailureConfig:
        """
        Inject network partition.
        
        Isolate specified agents from others using docker network disconnect.
        
        isolated_agents: Agents to isolate (e.g., ["SAT-003-A", "SAT-004-A", "SAT-005-A"])
        remaining_agents: Agents on other side (e.g., ["SAT-001-A", "SAT-002-A"])
        
        Should trigger:
        - Reliable delivery failures between partitions
        - Health broadcasts blocked
        - Consensus votes only within partition
        - Quorum check: 3/5 on one side (majority has quorum), 2/5 on other (loses quorum)
        """
        config = FailureConfig(
            failure_type=FailureType.NETWORK_PARTITION,
            target_agents=isolated_agents + remaining_agents,
            duration_seconds=duration_seconds,
            recovery_method="heal",
            expected_impact="Network split, quorum on majority side, consensus blocked on minority"
        )
        
        try:
            network = self.docker.networks.get("isl-net")
            logger.warning(
                f"INJECTING: Network partition "
                f"(isolated={isolated_agents}, remaining={remaining_agents})"
            )
            
            # Disconnect isolated agents from network
            for agent_id in isolated_agents:
                container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                network.disconnect(container)
                logger.info(f"Disconnected {agent_id} from isl-net")
            
            self.active_failures["_partition"] = config
            
            # Schedule healing
            if duration_seconds:
                task = asyncio.create_task(
                    self._heal_partition(isolated_agents, duration_seconds)
                )
                self.recovery_tasks["_partition"] = task
        except Exception as e:
            logger.error(f"Failed to create partition: {e}")
            raise
        
        return config
    
    async def inject_network_latency(
        self,
        agent_id: str,
        latency_ms: float,
        jitter_ms: float = 0.0,
        duration_seconds: Optional[int] = None
    ) -> FailureConfig:
        """
        Inject network latency using tc (traffic control).
        
        Simulates slow ISL by adding delay to packets.
        Normal ISL: 120ms
        Injected: latency_ms + jitter
        
        Should trigger:
        - Increased consensus time
        - Potential timeout if latency > timeout
        - Quorum still works but slower
        """
        config = FailureConfig(
            failure_type=FailureType.NETWORK_LATENCY,
            target_agents=[agent_id],
            duration_seconds=duration_seconds,
            intensity=(latency_ms - 120) / 500,  # Normalize
            recovery_method="heal",
            expected_impact="Higher latency, consensus slower, quorum still works"
        )
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(f"INJECTING: Network latency on {agent_id} ({latency_ms}ms)")
            
            # Use tc to add latency
            cmd = (
                f"tc qdisc add dev eth0 root netem "
                f"delay {int(latency_ms)}ms {int(jitter_ms)}ms distribution normal"
            )
            container.exec_run(cmd)
            self.active_failures[agent_id] = config
            
            if duration_seconds:
                task = asyncio.create_task(
                    self._heal_latency(agent_id, duration_seconds)
                )
                self.recovery_tasks[agent_id] = task
        except Exception as e:
            logger.error(f"Failed to inject latency on {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_packet_loss(
        self,
        agent_id: str,
        loss_percent: float,
        duration_seconds: Optional[int] = None
    ) -> FailureConfig:
        """
        Inject packet loss using tc.
        
        Simulates lossy ISL (normal: 5%, extreme: 20%+)
        
        Should trigger:
        - Reliable delivery retries (#403)
        - Increased latency due to retransmissions
        - Potential consensus timeouts if loss too high
        """
        config = FailureConfig(
            failure_type=FailureType.NETWORK_LOSS,
            target_agents=[agent_id],
            duration_seconds=duration_seconds,
            intensity=loss_percent / 100.0,
            recovery_method="heal",
            expected_impact="Packet loss, reliable delivery retries, latency increases"
        )
        
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            logger.warning(f"INJECTING: Packet loss on {agent_id} ({loss_percent}%)")
            
            # Clear old qdisc first
            try:
                container.exec_run("tc qdisc del dev eth0 root")
            except:
                pass
            
            # Add loss
            cmd = f"tc qdisc add dev eth0 root netem loss {loss_percent}%"
            container.exec_run(cmd)
            self.active_failures[agent_id] = config
            
            if duration_seconds:
                task = asyncio.create_task(
                    self._heal_loss(agent_id, duration_seconds)
                )
                self.recovery_tasks[agent_id] = task
        except Exception as e:
            logger.error(f"Failed to inject packet loss on {agent_id}: {e}")
            raise
        
        return config
    
    async def inject_bus_down(self, duration_seconds: Optional[int] = None) -> FailureConfig:
        """
        Inject event bus (RabbitMQ) failure.
        
        Should trigger:
        - Health broadcasts fail (some messages queued)
        - Leader election blocked (needs bus)
        - Graceful degradation if bus comes back
        - Timeouts on pending broadcasts
        """
        config = FailureConfig(
            failure_type=FailureType.BUS_DOWN,
            target_agents=["all"],
            duration_seconds=duration_seconds,
            recovery_method="restart",
            expected_impact="Event bus down, agents lose coordination, potential timeout cascades"
        )
        
        try:
            container = self.docker.containers.get("astra-event-bus")
            logger.critical("INJECTING: Event bus down!")
            container.stop()
            self.active_failures["bus"] = config
            
            if duration_seconds:
                task = asyncio.create_task(
                    self._recover_bus(duration_seconds)
                )
                self.recovery_tasks["bus"] = task
        except Exception as e:
            logger.error(f"Failed to stop event bus: {e}")
            raise
        
        return config
    
    async def inject_registry_down(self, duration_seconds: Optional[int] = None) -> FailureConfig:
        """
        Inject registry (Redis) failure.
        
        Should trigger:
        - SwarmRegistry can't update peer list
        - Leader election may block
        - In-memory caching keeps some info
        - Recovery when redis back up
        """
        config = FailureConfig(
            failure_type=FailureType.REGISTRY_DOWN,
            target_agents=["all"],
            duration_seconds=duration_seconds,
            recovery_method="restart",
            expected_impact="Registry down, peer discovery fails, uses cached info"
        )
        
        try:
            container = self.docker.containers.get("astra-redis")
            logger.critical("INJECTING: Registry (Redis) down!")
            container.stop()
            self.active_failures["registry"] = config
            
            if duration_seconds:
                task = asyncio.create_task(
                    self._recover_registry(duration_seconds)
                )
                self.recovery_tasks["registry"] = task
        except Exception as e:
            logger.error(f"Failed to stop registry: {e}")
            raise
        
        return config
    
    async def inject_cascading_failure(
        self,
        initial_agent: str,
        cascade_list: List[str],
        delay_between_ms: int = 1000
    ) -> FailureConfig:
        """
        Inject cascading failures (agents fail in sequence).
        
        Simulates scenario where one agent failure triggers others.
        Can test if quorum maintained or if it's lost.
        
        Example: Crash SAT-001, then SAT-002 crashes (due to leader election overhead?), etc.
        """
        config = FailureConfig(
            failure_type=FailureType.CASCADING_FAILURE,
            target_agents=[initial_agent] + cascade_list,
            recovery_method="manual",
            expected_impact="Multiple agents fail in sequence, tests recovery limits"
        )
        
        logger.warning(f"INJECTING: Cascading failure starting with {initial_agent}")
        
        # First agent crashes
        await self.inject_agent_crash(initial_agent)
        
        # Then others fail in sequence
        for agent_id in cascade_list:
            await asyncio.sleep(delay_between_ms / 1000)
            try:
                logger.warning(f"CASCADING: Crashing {agent_id}")
                await self.inject_agent_crash(agent_id)
            except:
                pass
        
        self.active_failures["cascade"] = config
        return config
    
    # ==================== RECOVERY METHODS ====================
    
    async def recover_all(self):
        """Recover from all active failures."""
        logger.info("Recovering all failures...")
        for failure_key in list(self.active_failures.keys()):
            await self.recover_failure(failure_key)
    
    async def recover_failure(self, failure_key: str):
        """Recover from specific failure."""
        if failure_key not in self.active_failures:
            return
        
        config = self.active_failures[failure_key]
        logger.info(f"Recovering failure: {failure_key} ({config.failure_type.value})")
        
        # Cancel recovery task if exists
        if failure_key in self.recovery_tasks:
            self.recovery_tasks[failure_key].cancel()
            del self.recovery_tasks[failure_key]
        
        try:
            if config.failure_type == FailureType.AGENT_CRASH:
                for agent_id in config.target_agents:
                    container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                    container.restart()
                    logger.info(f"Restarted {agent_id}")
            
            elif config.failure_type == FailureType.AGENT_HANG:
                for agent_id in config.target_agents:
                    container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                    container.kill(signal="SIGCONT")  # Resume process
                    logger.info(f"Resumed {agent_id}")
            
            elif config.failure_type == FailureType.NETWORK_PARTITION:
                network = self.docker.networks.get("isl-net")
                for agent_id in config.target_agents:
                    try:
                        container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                        network.connect(container)
                        logger.info(f"Reconnected {agent_id}")
                    except:
                        pass
            
            elif config.failure_type in [FailureType.NETWORK_LATENCY, FailureType.NETWORK_LOSS]:
                for agent_id in config.target_agents:
                    container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                    try:
                        container.exec_run("tc qdisc del dev eth0 root")
                        logger.info(f"Removed traffic control from {agent_id}")
                    except:
                        pass
            
            elif config.failure_type == FailureType.BUS_DOWN:
                container = self.docker.containers.get("astra-event-bus")
                container.start()
                logger.info("Event bus restarted")
            
            elif config.failure_type == FailureType.REGISTRY_DOWN:
                container = self.docker.containers.get("astra-redis")
                container.start()
                logger.info("Registry restarted")
        
        except Exception as e:
            logger.error(f"Recovery failed for {failure_key}: {e}")
        
        finally:
            del self.active_failures[failure_key]
    
    # ==================== SCHEDULED RECOVERY ====================
    
    async def _recover_hang(self, agent_id: str, duration_seconds: int):
        """Scheduled recovery from hang."""
        await asyncio.sleep(duration_seconds)
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            container.kill(signal="SIGCONT")
            logger.info(f"Auto-recovered hang on {agent_id}")
        except:
            pass
    
    async def _recover_memory_leak(self, agent_id: str, duration_seconds: int):
        """Scheduled recovery from memory leak."""
        await asyncio.sleep(duration_seconds)
        # Could restart agent or just let memory grow (for testing)
    
    async def _heal_partition(self, isolated_agents: List[str], duration_seconds: int):
        """Scheduled healing of partition."""
        await asyncio.sleep(duration_seconds)
        try:
            network = self.docker.networks.get("isl-net")
            for agent_id in isolated_agents:
                container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                network.connect(container)
                logger.info(f"Reconnected {agent_id}")
        except:
            pass
    
    async def _heal_latency(self, agent_id: str, duration_seconds: int):
        """Scheduled removal of latency."""
        await asyncio.sleep(duration_seconds)
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            container.exec_run("tc qdisc del dev eth0 root")
            logger.info(f"Removed latency from {agent_id}")
        except:
            pass
    
    async def _heal_loss(self, agent_id: str, duration_seconds: int):
        """Scheduled removal of packet loss."""
        await asyncio.sleep(duration_seconds)
        try:
            container = self.docker.containers.get(f"astra-{agent_id.lower()}")
            container.exec_run("tc qdisc del dev eth0 root")
            logger.info(f"Removed packet loss from {agent_id}")
        except:
            pass
    
    async def _recover_bus(self, duration_seconds: int):
        """Scheduled restart of event bus."""
        await asyncio.sleep(duration_seconds)
        try:
            container = self.docker.containers.get("astra-event-bus")
            container.start()
            logger.info("Event bus auto-recovered")
        except:
            pass
    
    async def _recover_registry(self, duration_seconds: int):
        """Scheduled restart of registry."""
        await asyncio.sleep(duration_seconds)
        try:
            container = self.docker.containers.get("astra-redis")
            container.start()
            logger.info("Registry auto-recovered")
        except:
            pass
