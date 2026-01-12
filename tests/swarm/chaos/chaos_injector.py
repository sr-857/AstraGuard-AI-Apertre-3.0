"""
Chaos Injector Extensions

Issue #415: Swarm chaos engineering suite
Extends failure_injector.py with advanced chaos methods:
- Packet loss injection (50%)
- Bandwidth exhaustion (2x normal)
- Agent churn (kill/respawn cycles)
- Latency cascades (compound failures)
"""

import asyncio
import subprocess
import time
from typing import List, Dict, Any
import docker


class ChaosInjectorExtensions:
    """Advanced chaos injection methods for swarm resilience testing."""
    
    def __init__(self, docker_client: docker.DockerClient = None):
        """Initialize chaos injector with docker client."""
        self.docker = docker_client or docker.from_env()
        self.active_chaos = {}  # Track active chaos scenarios
    
    # ==================== PACKET LOSS INJECTION ====================
    
    async def inject_packet_loss(
        self,
        network: str = "isl-net",
        percentage: int = 50,
        duration_seconds: int = 60
    ) -> str:
        """
        Inject packet loss on ISL network.
        
        Args:
            network: Docker network name
            percentage: Packet loss percentage (1-100)
            duration_seconds: How long to maintain
            
        Returns:
            Chaos ID for tracking
        """
        chaos_id = f"packet_loss_{int(time.time())}"
        
        try:
            # Apply packet loss to each agent container
            containers = self.docker.containers.list(
                filters={"network": network}
            )
            
            for container in containers:
                # Apply tc (traffic control) for packet loss
                cmd = f"tc qdisc add dev eth0 root netem loss {percentage}%"
                try:
                    container.exec_run(cmd, privileged=True)
                except:
                    # Try alternative command
                    cmd = f"tc qdisc replace dev eth0 root netem loss {percentage}%"
                    container.exec_run(cmd, privileged=True)
            
            # Store chaos metadata
            self.active_chaos[chaos_id] = {
                "type": "packet_loss",
                "percentage": percentage,
                "network": network,
                "start_time": time.time(),
                "duration": duration_seconds,
                "containers": [c.name for c in containers]
            }
            
            return chaos_id
        
        except Exception as e:
            raise RuntimeError(f"Failed to inject packet loss: {e}")
    
    async def recover_packet_loss(self, network: str = "isl-net"):
        """Remove packet loss from ISL network."""
        try:
            containers = self.docker.containers.list(
                filters={"network": network}
            )
            
            for container in containers:
                # Remove qdisc rules
                cmd = "tc qdisc del dev eth0 root"
                try:
                    container.exec_run(cmd, privileged=True)
                except:
                    pass  # Already removed
            
            # Clean up chaos tracking
            to_remove = [
                k for k, v in self.active_chaos.items()
                if v["type"] == "packet_loss" and v["network"] == network
            ]
            for k in to_remove:
                del self.active_chaos[k]
        
        except Exception as e:
            raise RuntimeError(f"Failed to recover from packet loss: {e}")
    
    # ==================== LATENCY CASCADE INJECTION ====================
    
    async def inject_latency_cascade(
        self,
        agents: List[str],
        initial_latency_ms: int = 100,
        cascade_step_ms: int = 50,
        duration_seconds: int = 60
    ) -> str:
        """
        Inject cascading latency (each agent has higher latency).
        Simulates propagation delays and compound network effects.
        
        Args:
            agents: List of agent IDs to cascade latency on
            initial_latency_ms: Starting latency
            cascade_step_ms: Increment per agent
            duration_seconds: Total duration
            
        Returns:
            Chaos ID
        """
        chaos_id = f"latency_cascade_{int(time.time())}"
        
        try:
            containers = self.docker.containers.list()
            container_map = {c.name: c for c in containers}
            
            for idx, agent_id in enumerate(agents):
                latency = initial_latency_ms + (idx * cascade_step_ms)
                
                # Find container (names are like "astra-sat-001-a")
                container_name = f"astra-{agent_id.lower()}"
                container = container_map.get(container_name)
                
                if not container:
                    continue
                
                cmd = f"tc qdisc add dev eth0 root netem delay {latency}ms"
                try:
                    container.exec_run(cmd, privileged=True)
                except:
                    cmd = f"tc qdisc replace dev eth0 root netem delay {latency}ms"
                    container.exec_run(cmd, privileged=True)
            
            self.active_chaos[chaos_id] = {
                "type": "latency_cascade",
                "agents": agents,
                "initial_latency": initial_latency_ms,
                "step": cascade_step_ms,
                "start_time": time.time(),
                "duration": duration_seconds
            }
            
            return chaos_id
        
        except Exception as e:
            raise RuntimeError(f"Failed to inject latency cascade: {e}")
    
    # ==================== BANDWIDTH EXHAUSTION ====================
    
    async def inject_bandwidth_exhaustion(
        self,
        agent_id: str,
        traffic_multiplier: float = 2.0,
        duration_seconds: int = 60
    ) -> str:
        """
        Exhaust bandwidth on specific agent (simulate congestion).
        
        Args:
            agent_id: Target agent (e.g., "SAT-001-A")
            traffic_multiplier: 2.0 = 2x normal traffic
            duration_seconds: How long to run
            
        Returns:
            Chaos ID
        """
        chaos_id = f"bandwidth_exhaust_{int(time.time())}"
        
        try:
            # Limit bandwidth to simulate congestion
            containers = self.docker.containers.list()
            container_map = {c.name: c for c in containers}
            
            container_name = f"astra-{agent_id.lower()}"
            container = container_map.get(container_name)
            
            if not container:
                raise RuntimeError(f"Container {container_name} not found")
            
            # Use tc to limit bandwidth
            # Normal: assume 1Mbps, limit to 0.5Mbps to simulate congestion
            rate_kbps = int(500 / traffic_multiplier)  # 500 kbps normal
            
            cmd = f"tc qdisc add dev eth0 root tbf rate {rate_kbps}kbit burst 32kbit latency 400ms"
            try:
                container.exec_run(cmd, privileged=True)
            except:
                cmd = f"tc qdisc replace dev eth0 root tbf rate {rate_kbps}kbit burst 32kbit latency 400ms"
                container.exec_run(cmd, privileged=True)
            
            self.active_chaos[chaos_id] = {
                "type": "bandwidth_exhaustion",
                "agent": agent_id,
                "multiplier": traffic_multiplier,
                "start_time": time.time(),
                "duration": duration_seconds
            }
            
            return chaos_id
        
        except Exception as e:
            raise RuntimeError(f"Failed to exhaust bandwidth: {e}")
    
    # ==================== AGENT CHURN ====================
    
    async def inject_agent_churn(
        self,
        agents: List[str],
        kill_delay_seconds: int = 5,
        restart_delay_seconds: int = 10,
        cycles: int = 2
    ) -> str:
        """
        Inject agent churn (kill and restart agents multiple times).
        Tests role reassignment and recovery resilience.
        
        Args:
            agents: List of agent IDs to churn
            kill_delay_seconds: Delay before kill
            restart_delay_seconds: Delay before restart
            cycles: Number of kill/restart cycles
            
        Returns:
            Chaos ID
        """
        chaos_id = f"agent_churn_{int(time.time())}"
        
        try:
            containers = self.docker.containers.list()
            container_map = {c.name: c for c in containers}
            
            self.active_chaos[chaos_id] = {
                "type": "agent_churn",
                "agents": agents,
                "cycles": cycles,
                "start_time": time.time(),
                "killed": [],
                "restarted": []
            }
            
            # Run churn in background
            asyncio.create_task(
                self._churn_loop(
                    container_map,
                    agents,
                    kill_delay_seconds,
                    restart_delay_seconds,
                    cycles,
                    chaos_id
                )
            )
            
            return chaos_id
        
        except Exception as e:
            raise RuntimeError(f"Failed to inject agent churn: {e}")
    
    async def _churn_loop(
        self,
        container_map: Dict[str, Any],
        agents: List[str],
        kill_delay: int,
        restart_delay: int,
        cycles: int,
        chaos_id: str
    ):
        """Run agent churn loop."""
        try:
            for cycle in range(cycles):
                for agent_id in agents:
                    container_name = f"astra-{agent_id.lower()}"
                    container = container_map.get(container_name)
                    
                    if not container:
                        continue
                    
                    # Kill
                    await asyncio.sleep(kill_delay)
                    container.kill()
                    self.active_chaos[chaos_id]["killed"].append(agent_id)
                    
                    # Restart
                    await asyncio.sleep(restart_delay)
                    container.restart()
                    self.active_chaos[chaos_id]["restarted"].append(agent_id)
        
        except Exception as e:
            pass  # Chaos continues
    
    # ==================== CASCADING FAILURE ====================
    
    async def inject_cascading_failure(
        self,
        agents: List[str],
        delay_between_failures_ms: int = 500,
        recovery_delay_seconds: int = 30
    ) -> str:
        """
        Inject cascading failure (agents fail in sequence).
        Tests safety mechanisms and no-cascading-failure invariant.
        
        Args:
            agents: Agents to fail in sequence
            delay_between_failures_ms: Milliseconds between failures
            recovery_delay_seconds: When to auto-recover
            
        Returns:
            Chaos ID
        """
        chaos_id = f"cascading_{int(time.time())}"
        
        try:
            containers = self.docker.containers.list()
            container_map = {c.name: c for c in containers}
            
            self.active_chaos[chaos_id] = {
                "type": "cascading_failure",
                "agents": agents,
                "start_time": time.time(),
                "failed": []
            }
            
            # Trigger cascading failures
            for agent_id in agents:
                container_name = f"astra-{agent_id.lower()}"
                container = container_map.get(container_name)
                
                if container:
                    container.kill()
                    self.active_chaos[chaos_id]["failed"].append(agent_id)
                
                await asyncio.sleep(delay_between_failures_ms / 1000.0)
            
            # Auto-recovery after delay
            asyncio.create_task(
                self._cascade_recover(container_map, agents, recovery_delay_seconds)
            )
            
            return chaos_id
        
        except Exception as e:
            raise RuntimeError(f"Failed to inject cascading failure: {e}")
    
    async def _cascade_recover(
        self,
        container_map: Dict[str, Any],
        agents: List[str],
        delay: int
    ):
        """Recover from cascading failure after delay."""
        await asyncio.sleep(delay)
        for agent_id in agents:
            container_name = f"astra-{agent_id.lower()}"
            container = container_map.get(container_name)
            if container:
                try:
                    container.restart()
                except:
                    pass
    
    # ==================== RECOVERY METHODS ====================
    
    async def recover_all(self):
        """Recover from all active chaos scenarios."""
        try:
            containers = self.docker.containers.list()
            
            for container in containers:
                # Remove all qdisc rules
                for cmd in [
                    "tc qdisc del dev eth0 root",
                    "tc qdisc del dev eth1 root",
                ]:
                    try:
                        container.exec_run(cmd, privileged=True)
                    except:
                        pass
            
            self.active_chaos.clear()
        
        except Exception as e:
            pass  # Continue recovery
    
    async def recover_chaos(self, chaos_id: str):
        """Recover from specific chaos scenario."""
        if chaos_id not in self.active_chaos:
            return
        
        chaos = self.active_chaos[chaos_id]
        
        try:
            if chaos["type"] == "packet_loss":
                await self.recover_packet_loss(chaos.get("network", "isl-net"))
            
            elif chaos["type"] == "latency_cascade":
                containers = self.docker.containers.list()
                for container in containers:
                    try:
                        container.exec_run("tc qdisc del dev eth0 root", privileged=True)
                    except:
                        pass
            
            elif chaos["type"] == "bandwidth_exhaustion":
                containers = self.docker.containers.list()
                for container in containers:
                    try:
                        container.exec_run("tc qdisc del dev eth0 root", privileged=True)
                    except:
                        pass
            
            del self.active_chaos[chaos_id]
        
        except Exception as e:
            pass
    
    def get_active_chaos(self) -> Dict[str, Any]:
        """Get all active chaos scenarios."""
        return dict(self.active_chaos)
    
    def get_chaos_status(self, chaos_id: str) -> Dict[str, Any]:
        """Get status of specific chaos scenario."""
        if chaos_id not in self.active_chaos:
            return {}
        
        chaos = self.active_chaos[chaos_id]
        elapsed = time.time() - chaos.get("start_time", time.time())
        
        return {
            **chaos,
            "elapsed_seconds": int(elapsed),
            "is_active": elapsed < chaos.get("duration", float("inf"))
        }
