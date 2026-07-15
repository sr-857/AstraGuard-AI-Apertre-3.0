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
    # Adjust path based on project structure (src/backend vs backend/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Go up from tests/backend/orchestration to root (tests/backend/orchestration -> project_root)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to find src directory (up 3 levels: orchestration -> backend -> tests -> root)
    root_dir = os.path.abspath(os.path.join(current_dir, '../../..'))
    src_backend_dir = os.path.join(root_dir, 'src', 'backend')
    
    # Check if src/backend exists, otherwise fallback
    if os.path.exists(src_backend_dir):
        orchestration_dir = os.path.join(src_backend_dir, 'orchestration')
    else:
        orchestration_dir = os.path.abspath(os.path.join(current_dir, '../../../backend/orchestration'))

    assert os.path.exists(os.path.join(orchestration_dir, '__init__.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'recovery_orchestrator.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'recovery_orchestrator_enhanced.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'distributed_coordinator.py'))
    assert os.path.exists(os.path.join(orchestration_dir, 'README.md'))

def test_compatibility_shims_exist():
    """Test that backward compatibility shims exist."""
    # Check for recovery_orchestrator.py in backend root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, '../../..'))
    
    src_backend_dir = os.path.join(root_dir, 'src', 'backend')
    if os.path.exists(src_backend_dir):
        backend_dir = src_backend_dir
    else:
        backend_dir = os.path.abspath(os.path.join(current_dir, '../../../backend'))
        
    assert os.path.exists(os.path.join(backend_dir, 'recovery_orchestrator.py'))
    assert os.path.exists(os.path.join(backend_dir, 'recovery_orchestrator_enhanced.py'))
    assert os.path.exists(os.path.join(backend_dir, 'distributed_coordinator.py'))

if __name__ == '__main__':
    test_package_structure()
    test_compatibility_shims_exist()
    print("✓ All smoke tests passed")
