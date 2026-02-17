import sys
import os
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

print(f"[{time.strftime('%X')}] Importing api.service...", flush=True)
import api.service

async def main():
    print(f"[{time.strftime('%X')}] Starting initialize_components...", flush=True)
    
    # instrument initialize_components manually
    print(f"[{time.strftime('%X')}] Init StateMachine...", flush=True)
    if api.service.state_machine is None:
        from state_machine.state_engine import StateMachine
        api.service.state_machine = StateMachine()
        
    print(f"[{time.strftime('%X')}] Init PolicyLoader...", flush=True)
    if api.service.policy_loader is None:
        from config.mission_phase_policy_loader import MissionPhasePolicyLoader
        api.service.policy_loader = MissionPhasePolicyLoader()
        
    print(f"[{time.strftime('%X')}] Init Handler...", flush=True)
    if api.service.phase_aware_handler is None:
        from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
        api.service.phase_aware_handler = PhaseAwareAnomalyHandler(api.service.state_machine, api.service.policy_loader)
        
    print(f"[{time.strftime('%X')}] Init MemoryStore...", flush=True)
    if api.service.memory_store is None:
        from memory_engine.memory_store import AdaptiveMemoryStore
        api.service.memory_store = AdaptiveMemoryStore()
        
    print(f"[{time.strftime('%X')}] Init PredictiveEngine...", flush=True)
    if api.service.predictive_engine is None:
        from security_engine.predictive_maintenance import get_predictive_maintenance_engine
        api.service.predictive_engine = await get_predictive_maintenance_engine(api.service.memory_store)
        
    print(f"[{time.strftime('%X')}] Done!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
