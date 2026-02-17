import pytest
from unittest.mock import Mock, patch, PropertyMock
from src.core.diagnostics import SystemDiagnostics

@pytest.fixture
def mock_psutil():
    with patch('src.core.diagnostics.psutil') as mock:
        # CPU
        mock.cpu_count.return_value = 4
        mock.boot_time.return_value = 1600000000.0
        mock.cpu_percent.side_effect = lambda interval=None, percpu=False: [10.0, 20.0, 10.0, 20.0] if percpu else 15.0
        
        # Memory
        mock.virtual_memory.return_value = Mock(total=1000, available=500, percent=50.0, used=500)
        mock.swap_memory.return_value = Mock(total=2000, used=0, percent=0.0)
        
        # Disk
        mock.disk_usage.return_value = Mock(total=10000, used=5000, free=5000, percent=50.0)
        
        # Network
        mock.net_io_counters.return_value = Mock(
            bytes_sent=100, bytes_recv=200,
            packets_sent=10, packets_recv=20,
            errin=0, errout=0
        )
        
        # Process
        mock_proc = Mock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "python"
        mock_proc.status.return_value = "running"
        mock_proc.cpu_percent.return_value = 1.5
        mock_proc.memory_percent.return_value = 0.5
        mock_proc.num_threads.return_value = 3
        mock_proc.open_files.return_value = []
        mock_proc.create_time.return_value = 1600000000.0
        
        mock.Process.return_value = mock_proc
        
        yield mock

def test_system_info(mock_psutil):
    diag = SystemDiagnostics()
    info = diag.get_system_info()
    
    assert info['cpu_count'] == 4
    assert 'os' in info
    assert 'python_version' in info

def test_resource_usage(mock_psutil):
    diag = SystemDiagnostics()
    res = diag.get_resource_usage()
    
    assert res['cpu']['total_percent'] == 15.0
    assert len(res['cpu']['per_core']) == 4
    
    assert res['memory']['total'] == 1000
    assert res['memory']['percent'] == 50.0
    
    assert res['disk_root']['percent'] == 50.0

def test_network_info(mock_psutil):
    diag = SystemDiagnostics()
    net = diag.get_network_info()
    
    assert net['bytes_sent'] == 100
    assert net['packets_recv'] == 20

def test_process_info(mock_psutil):
    diag = SystemDiagnostics()
    proc = diag.get_process_info()
    
    assert proc['pid'] == 1234
    assert proc['status'] == "running"
    assert proc['cpu_percent'] == 1.5

def test_full_diagnostics(mock_psutil):
    diag = SystemDiagnostics()
    report = diag.run_full_diagnostics()
    
    assert 'timestamp' in report
    assert 'system_info' in report
    assert 'resources' in report
    assert 'network' in report
    assert 'process' in report
    assert 'application_health' in report
