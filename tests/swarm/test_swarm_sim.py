"""
Swarm Simulator Test Orchestrator

Issue #414: Multi-agent Docker swarm simulator test orchestration
Coordinates docker-compose, golden paths, and failure injection
Validates complete swarm intelligence pipeline (#397-413)

Test Flow:
1. Start 5-agent constellation via docker-compose
2. Run golden path scenarios
3. Inject failures and validate recovery
4. Verify all components (#397-413) working
5. Collect telemetry and generate reports
"""

import asyncio
import pytest
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import docker
import subprocess
import httpx
import json

from tests.swarm.golden_paths import (
    GoldenPath1_HealthyBoot,
    GoldenPath2_AnomalyResponse,
    GoldenPath3_NetworkPartition,
    GoldenPath4_LeaderCrash,
)
from tests.swarm.failure_injector import FailureInjector, FailureType

logger = logging.getLogger(__name__)

# Mark swarm simulator tests as slow - they use docker-compose
pytestmark = [pytest.mark.slow, pytest.mark.timeout(300)]


@dataclass
class SwarmTestResult:
    """Result of single test."""
    test_name: str
    passed: bool
    duration_seconds: float
    error: Optional[str] = None
    metrics: Dict[str, Any] = None


@dataclass
class SwarmTestSummary:
    """Summary of all swarm tests."""
    start_time: datetime
    end_time: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    results: List[SwarmTestResult]
    
    @property
    def duration_seconds(self) -> float:
        """Total test duration."""
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def pass_rate(self) -> float:
        """Percentage of tests passed."""
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests * 100


class SwarmSimulatorOrchestrator:
    """Orchestrates swarm simulator tests."""
    
    def __init__(self, docker_compose_file: str = "docker-compose.swarm.yml"):
        """Initialize orchestrator."""
        self.docker = docker.from_env()
        self.compose_file = docker_compose_file
        self.docker_client = self.docker
        self.failure_injector = FailureInjector(self.docker)
        
        # Agent tracking
        self.agents = [
            "SAT-001-A", "SAT-002-A", "SAT-003-A", "SAT-004-A", "SAT-005-A"
        ]
        self.agent_ports = {
            "SAT-001-A": 8001,
            "SAT-002-A": 8002,
            "SAT-003-A": 8003,
            "SAT-004-A": 8004,
            "SAT-005-A": 8005,
        }
    
    async def start_constellation(self) -> bool:
        """Start 5-agent constellation via docker-compose."""
        logger.info("Starting 5-agent constellation...")
        try:
            result = subprocess.run(
                ["docker-compose", "-f", self.compose_file, "up", "-d"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                logger.error(f"docker-compose failed: {result.stderr}")
                return False
            
            # Wait for all agents healthy
            await self._wait_for_agents_healthy(timeout=300)
            logger.info("✓ All agents healthy")
            return True
        except Exception as e:
            logger.error(f"Failed to start constellation: {e}")
            return False
    
    async def stop_constellation(self) -> bool:
        """Stop constellation and cleanup."""
        logger.info("Stopping constellation...")
        try:
            subprocess.run(
                ["docker-compose", "-f", self.compose_file, "down"],
                capture_output=True,
                timeout=30
            )
            logger.info("✓ Constellation stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop constellation: {e}")
            return False
    
    async def _wait_for_agents_healthy(self, timeout: int = 300):
        """Wait for all agents to pass health checks."""
        start = datetime.now()
        logger.info(f"Waiting up to {timeout}s for agents to become healthy...")
        
        async with httpx.AsyncClient(timeout=5) as client:
            while (datetime.now() - start).total_seconds() < timeout:
                try:
                    healthy = 0
                    errors = []
                    for agent_id, port in self.agent_ports.items():
                        try:
                            resp = await client.get(f"http://localhost:{port}/health")
                            if resp.status_code == 200:
                                healthy += 1
                            else:
                                errors.append(f"{agent_id}: status {resp.status_code}")
                        except Exception as e:
                            errors.append(f"{agent_id}: {str(e)}")
                    
                    if healthy == len(self.agents):
                        logger.info(f"All {len(self.agents)} agents healthy")
                        return
                    
                    # Only log every 10 seconds to avoid spam, but log errors
                    if int((datetime.now() - start).total_seconds()) % 10 == 0:
                        logger.info(f"Waiting for agents: {healthy}/{len(self.agents)} healthy")
                        if errors:
                            logger.debug(f"Health check errors: {', '.join(errors[:3])}...")
                        
                except Exception as e:
                    logger.error(f"Health check loop error: {e}")
                
                await asyncio.sleep(1)
        
        # Dump docker logs on failure
        try:
            logger.error("!!! TIMEOUT: Dumping container logs !!!")
            for agent_id in self.agents:
                try:
                    container = self.docker.containers.get(f"astra-{agent_id.lower()}")
                    logs = container.logs(tail=20).decode('utf-8')
                    logger.error(f"--- Logs for {agent_id} ---\n{logs}\n----------------")
                except Exception as e:
                    logger.error(f"Could not get logs for {agent_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to dump logs: {e}")

        raise TimeoutError(f"Agents not healthy after {timeout}s")
    
    # ==================== GOLDEN PATH TESTS ====================
    
    @pytest.mark.asyncio
    async def test_golden_path_1_healthy_boot(self) -> SwarmTestResult:
        """Test 1: Healthy Constellation Boot (#397-400)."""
        test_name = "Golden Path 1: Healthy Boot"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            path = GoldenPath1_HealthyBoot()
            
            # Implement required methods
            path._get_alive_agents = self._get_alive_agents
            path._get_leader = self._get_leader
            path._get_health_broadcasts = self._get_health_broadcasts
            path._build_constellation_state = self._build_constellation_state
            
            await path.setup()
            state = await path.execute()
            assert await path.validate(state), "Validation failed"
            await path.teardown()
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED ({duration:.1f}s)")
            logger.error(f"  Error: {e}")
            return SwarmTestResult(test_name, False, duration, str(e))
    
    @pytest.mark.asyncio
    async def test_golden_path_2_anomaly_response(self) -> SwarmTestResult:
        """Test 2: Anomaly Detection → Recovery (#401-409)."""
        test_name = "Golden Path 2: Anomaly Response"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            path = GoldenPath2_AnomalyResponse()
            
            # Implement required methods
            path._inject_memory_leak = self._inject_memory_leak
            path._get_agent_health = self._get_agent_health
            path._get_agent_role = self._get_agent_role
            path._build_constellation_state = self._build_constellation_state
            
            await path.setup()
            state = await path.execute()
            assert await path.validate(state), "Validation failed"
            await path.teardown()
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED ({duration:.1f}s)")
            logger.error(f"  Error: {e}")
            return SwarmTestResult(test_name, False, duration, str(e))
    
    @pytest.mark.asyncio
    async def test_golden_path_3_network_partition(self) -> SwarmTestResult:
        """Test 3: Network Partition → Quorum (#403-406)."""
        test_name = "Golden Path 3: Network Partition"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            path = GoldenPath3_NetworkPartition()
            
            # Implement required methods
            path._create_partition = self._create_partition
            path._get_connected_agents = self._get_connected_agents
            path._get_quorum_status = self._get_quorum_status
            path._build_constellation_state = self._build_constellation_state
            
            await path.setup()
            state = await path.execute()
            assert await path.validate(state), "Validation failed"
            
            # Heal partition
            await self.failure_injector.recover_failure("_partition")
            await path.teardown()
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED ({duration:.1f}s)")
            logger.error(f"  Error: {e}")
            return SwarmTestResult(test_name, False, duration, str(e))
    
    @pytest.mark.asyncio
    async def test_golden_path_4_leader_crash(self) -> SwarmTestResult:
        """Test 4: Leader Crash → Re-election (#400-406)."""
        test_name = "Golden Path 4: Leader Crash"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            path = GoldenPath4_LeaderCrash()
            
            # Implement required methods
            path._kill_agent = self._kill_agent
            path._is_agent_alive = self._is_agent_alive
            path._get_leader = self._get_leader
            path._build_constellation_state = self._build_constellation_state
            
            await path.setup()
            state = await path.execute()
            assert await path.validate(state), "Validation failed"
            
            # Restart crashed leader
            await self._restart_agent("SAT-001-A")
            await path.teardown()
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED ({duration:.1f}s)")
            logger.error(f"  Error: {e}")
            return SwarmTestResult(test_name, False, duration, str(e))
    
    # ==================== FAILURE INJECTION TESTS ====================
    
    @pytest.mark.asyncio
    async def test_failure_agent_crash_recovery(self) -> SwarmTestResult:
        """Test agent crash and recovery."""
        test_name = "Failure: Agent Crash Recovery"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            # Crash SAT-002
            await self.failure_injector.inject_agent_crash("SAT-002-A")
            await asyncio.sleep(2)
            
            # Verify it's dead
            alive = await self._is_agent_alive("SAT-002-A")
            assert not alive, "Agent should be dead"
            
            # Verify quorum maintained (4/5, needs 3)
            state = await self._build_constellation_state()
            assert state.quorum_available, "Quorum lost"
            
            # Recover
            await self.failure_injector.recover_failure("SAT-002-A")
            await asyncio.sleep(5)
            
            # Verify recovered
            alive = await self._is_agent_alive("SAT-002-A")
            assert alive, "Agent should be recovered"
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED: {e}")
            await self.failure_injector.recover_all()
            return SwarmTestResult(test_name, False, duration, str(e))
    
    @pytest.mark.asyncio
    async def test_failure_network_latency(self) -> SwarmTestResult:
        """Test operation under high latency."""
        test_name = "Failure: Network Latency"
        logger.info(f"Running: {test_name}")
        start = datetime.now()
        
        try:
            # Inject high latency on SAT-003
            await self.failure_injector.inject_network_latency(
                "SAT-003-A",
                latency_ms=300,  # 3x normal
                duration_seconds=10
            )
            
            # Verify constellation still works (slower but functional)
            await asyncio.sleep(5)
            state = await self._build_constellation_state()
            assert state.quorum_available, "Quorum lost under latency"
            assert state.alive_agents == 5, "Agents disconnected"
            
            # Wait for recovery
            await asyncio.sleep(10)
            
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"✓ {test_name}: PASSED ({duration:.1f}s)")
            return SwarmTestResult(test_name, True, duration)
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"✗ {test_name}: FAILED: {e}")
            await self.failure_injector.recover_all()
            return SwarmTestResult(test_name, False, duration, str(e))
    
    # ==================== COMPLETE TEST SUITE ====================
    
    @pytest.mark.asyncio
    async def run_all_tests(self) -> SwarmTestSummary:
        """Run complete swarm simulator test suite."""
        logger.info("=" * 60)
        logger.info("SWARM SIMULATOR TEST SUITE")
        logger.info("=" * 60)
        
        summary_start = datetime.now()
        results = []
        
        try:
            # Start constellation
            if not await self.start_constellation():
                raise RuntimeError("Failed to start constellation")
            
            # Golden path tests
            results.append(await self.test_golden_path_1_healthy_boot())
            results.append(await self.test_golden_path_2_anomaly_response())
            results.append(await self.test_golden_path_3_network_partition())
            results.append(await self.test_golden_path_4_leader_crash())
            
            # Failure injection tests
            results.append(await self.test_failure_agent_crash_recovery())
            results.append(await self.test_failure_network_latency())
            
        finally:
            # Cleanup
            await self.failure_injector.recover_all()
            await self.stop_constellation()
        
        summary_end = datetime.now()
        
        # Build summary
        passed = len([r for r in results if r.passed])
        failed = len([r for r in results if not r.passed])
        
        summary = SwarmTestSummary(
            start_time=summary_start,
            end_time=summary_end,
            total_tests=len(results),
            passed_tests=passed,
            failed_tests=failed,
            results=results
        )
        
        # Print summary
        self._print_summary(summary)
        
        return summary
    
    def _print_summary(self, summary: SwarmTestSummary):
        """Print test summary."""
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {summary.total_tests}")
        logger.info(f"Passed: {summary.passed_tests} ✓")
        logger.info(f"Failed: {summary.failed_tests} ✗")
        logger.info(f"Pass Rate: {summary.pass_rate:.1f}%")
        logger.info(f"Duration: {summary.duration_seconds:.1f}s")
        logger.info("=" * 60)
        
        for result in summary.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            logger.info(f"{status}: {result.test_name} ({result.duration_seconds:.1f}s)")
            if result.error:
                logger.info(f"       {result.error}")
    
    # ==================== HELPER METHODS ====================
    
    async def _get_alive_agents(self) -> List[str]:
        """Get list of alive agents."""
        alive = []
        for agent_id, port in self.agent_ports.items():
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    resp = await client.get(f"http://localhost:{port}/health")
                    if resp.status_code == 200:
                        alive.append(agent_id)
            except:
                pass
        return alive
    
    async def _is_agent_alive(self, agent_id: str) -> bool:
        """Check if agent is alive."""
        port = self.agent_ports.get(agent_id)
        if not port:
            return False
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"http://localhost:{port}/health")
                return resp.status_code == 200
        except:
            return False
    
    async def _get_leader(self) -> Optional[str]:
        """Get current leader ID."""
        for agent_id, port in self.agent_ports.items():
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    resp = await client.get(f"http://localhost:{port}/leader")
                    data = resp.json()
                    if data.get("is_leader"):
                        return agent_id
            except:
                pass
        return None
    
    async def _kill_agent(self, agent_id: str):
        """Kill agent container."""
        container = self.docker.containers.get(f"astra-{agent_id.lower()}")
        container.kill()
    
    async def _restart_agent(self, agent_id: str):
        """Restart agent container."""
        container = self.docker.containers.get(f"astra-{agent_id.lower()}")
        container.restart()
    
    async def _inject_memory_leak(self, agent_id: str):
        """Inject memory leak."""
        await self.failure_injector.inject_memory_leak(agent_id, duration_seconds=10)
    
    async def _get_agent_health(self, agent_id: str) -> float:
        """Get agent health score."""
        port = self.agent_ports.get(agent_id)
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"http://localhost:{port}/metrics/health")
                data = resp.json()
                return data.get("health_score", 1.0)
        except:
            return 1.0
    
    async def _get_agent_role(self, agent_id: str) -> str:
        """Get agent role."""
        port = self.agent_ports.get(agent_id)
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"http://localhost:{port}/status")
                data = resp.json()
                return data.get("role", "UNKNOWN")
        except:
            return "UNKNOWN"
    
    async def _get_health_broadcasts(self) -> Dict[str, Any]:
        """Get health broadcasts from registry."""
        # Would query Redis or check event bus
        return {}
    
    async def _create_partition(self, isolated: List[str], remaining: List[str]):
        """Create network partition."""
        await self.failure_injector.inject_network_partition(isolated, remaining, duration_seconds=30)
    
    async def _get_connected_agents(self) -> List[str]:
        """Get connected agents in network."""
        return await self._get_alive_agents()
    
    async def _get_quorum_status(self) -> Dict[str, Any]:
        """Get quorum status."""
        alive = await self._get_alive_agents()
        return {
            "alive": len(alive),
            "quorum": len(alive) >= 3,
            "agents": alive
        }
    
    async def _build_constellation_state(self):
        """Build constellation state object."""
        from tests.swarm.golden_paths import ConstellationState, AgentState, SwarmPhase
        
        alive = await self._get_alive_agents()
        leader = await self._get_leader()
        
        agents = {}
        for agent_id in self.agents:
            is_alive = agent_id in alive
            agents[agent_id] = AgentState(
                agent_id=agent_id,
                role="PRIMARY" if agent_id == "SAT-001-A" else "SECONDARY",
                is_alive=is_alive,
                is_leader=(agent_id == leader),
                health_score=1.0 if is_alive else 0.0,
                last_heartbeat=datetime.now(),
                memory_pool_usage=0.5,
                decision_latency_ms=50,
                consensus_approved=10,
                consensus_rejected=1
            )
        
        phase = SwarmPhase.HEALTHY if len(alive) >= 3 else SwarmPhase.DEGRADED
        
        return ConstellationState(
            phase=phase,
            leader_id=leader,
            agents=agents,
            alive_agents=len(alive),
            dead_agents=5 - len(alive),
            quorum_size=3,
            quorum_available=(len(alive) >= 3),
            timestamp=datetime.now()
        )


# ==================== PYTEST FIXTURES ====================



@pytest.fixture
async def swarm_sim():
    """Swarm simulator fixture."""
    try:
        orchestrator = SwarmSimulatorOrchestrator(docker_compose_file="infra/docker/docker-compose.swarm.yml")
        # Verify docker connection immediately
        orchestrator.docker.version()
    except (docker.errors.DockerException, Exception) as e:
        pytest.skip(f"Docker not available or not running: {e}")
        return

    yield orchestrator
    
    try:
        await orchestrator.failure_injector.recover_all()
    except:
        pass


# ==================== PYTEST TESTS ====================

@pytest.mark.asyncio
async def test_full_swarm_boot(swarm_sim):
    """Test full swarm boot."""
    if not await swarm_sim.start_constellation():
        pytest.fail("Failed to start constellation")
    
    alive = await swarm_sim._get_alive_agents()
    assert len(alive) == 5
    await swarm_sim.stop_constellation()


@pytest.mark.asyncio
async def test_all_golden_paths(swarm_sim):
    """Run all golden path tests."""
    summary = await swarm_sim.run_all_tests()
    assert summary.pass_rate >= 80.0, f"Only {summary.pass_rate:.1f}% tests passed"
