"""
Simple smoke test for orchestration package without full imports.

This test validates the basic structure without triggering problematic imports.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_package_structure():
    """Test that orchestration package structure exists."""
    orchestration_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend', 'orchestration')
    
    assert os.path.exists(os.path.join(orchestration_dir, '__init__.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'orchestrator_base.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'coordinator.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'recovery_orchestrator.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'recovery_orchestrator_enhanced.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'distributed_coordinator.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'README.md'))

def test_compatibility_shims_exist():
    """Test that backward compatibility shims exist."""
    backend_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend')
    
    assert os.path.exists(os.path.join(backend_dir, 'recovery_orchestrator.py'))
    assert os.path.exists(os.path.join(backend_dir, 'recovery_orchestrator_enhanced.py'))
    assert os.path.exists(os.path.join(backend_dir, 'distributed_coordinator.py'))

if __name__ == '__main__':
    test_package_structure()
    test_compatibility_shims_exist()
    print("✓ All smoke tests passed")
