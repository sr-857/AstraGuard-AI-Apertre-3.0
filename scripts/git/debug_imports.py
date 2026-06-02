import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

print(f"[{time.strftime('%X')}] Starting import checks...", flush=True)

try:
    print(f"[{time.strftime('%X')}] Importing core.secrets...", flush=True)
    import core.secrets
    
    print(f"[{time.strftime('%X')}] Importing core.auth...", flush=True)
    import core.auth
    
    print(f"[{time.strftime('%X')}] Importing state_machine.state_engine...", flush=True)
    import state_machine.state_engine
    
    print(f"[{time.strftime('%X')}] Importing config.mission_phase_policy_loader...", flush=True)
    import config.mission_phase_policy_loader
    
    print(f"[{time.strftime('%X')}] Importing anomaly_agent.phase_aware_handler...", flush=True)
    import anomaly_agent.phase_aware_handler
    
    print(f"[{time.strftime('%X')}] Importing anomaly.anomaly_detector...", flush=True)
    import anomaly.anomaly_detector
    
    print(f"[{time.strftime('%X')}] Importing classifier.fault_classifier...", flush=True)
    import classifier.fault_classifier
    
    print(f"[{time.strftime('%X')}] Importing core.component_health...", flush=True)
    import core.component_health
    
    print(f"[{time.strftime('%X')}] Importing memory_engine.memory_store...", flush=True)
    import memory_engine.memory_store
    
    print(f"[{time.strftime('%X')}] Importing security_engine.predictive_maintenance...", flush=True)
    import security_engine.predictive_maintenance
    
    print(f"[{time.strftime('%X')}] Importing backend.redis_client...", flush=True)
    import backend.redis_client
    
    print(f"[{time.strftime('%X')}] Importing api.service...", flush=True)
    import api.service
    
    print(f"[{time.strftime('%X')}] Done!", flush=True)

except Exception as e:
    print(f"\n[ERROR] Failed to import: {e}", flush=True)
    import traceback
    traceback.print_exc()

except KeyboardInterrupt:
    print("\n[INTERRUPTED] Import interrupted by user.", flush=True)
