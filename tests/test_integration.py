import time
from pathlib import Path
import pytest
from monitoring.rad_logs_monitor import RadLogsMonitor

@pytest.fixture
def logs_dir(tmp_path):
    """Creates a temporary logs directory structure."""
    device_dir = tmp_path / "device1"
    device_dir.mkdir()
    return tmp_path

def test_monitor_integration(logs_dir):
    monitor = RadLogsMonitor(str(logs_dir))
    
    # 1. Initial scan (one empty device folder exists)
    monitor.initial_scan()
    assert len(monitor.device_data) == 1
    assert "device1" in monitor.device_data
    assert monitor.device_data["device1"]["sdcs"] == 0
    
    # 2. Create a new log file
    log_file = logs_dir / "device1" / "test.log"
    log_content = "#HEADER model=test_model.tflite\n#BEGIN Y:2024 M:01 D:01 Time:00:00:00\nAccTime:10.0\nSDC detected\n"
    log_file.write_text(log_content)
    
    # Simulate Watchdog event triggering process_updates (in a real app, the handler calls this)
    # For testing, we can just call process_updates()
    # But wait, RadLogsMonitor.process_updates() processes the queue of changed files.
    # The LogChangeHandler adds to this queue.
    
    from monitoring.watcher import LogChangeHandler
    handler = LogChangeHandler(monitor)
    
    # Manually trigger the handler for the new file
    class MockEvent:
        def __init__(self, src_path):
            self.src_path = src_path
            self.is_directory = False

    handler.on_created(MockEvent(str(log_file)))
    handler.on_modified(MockEvent(str(log_file)))
    
    monitor.process_updates()
    
    # Verify data extraction
    assert "device1" in monitor.device_data
    assert monitor.device_data["device1"]["sdcs"] == 1
    assert "test_model.tflite" in monitor.model_data
    assert monitor.model_data["test_model.tflite"]["sdcs"] == 1
    
    # 3. Append more data (another SDC)
    with open(log_file, "a") as f:
        f.write("AccTime:20.0\nSDC again\n")
    
    handler.on_modified(MockEvent(str(log_file)))
    monitor.process_updates()
    
    assert monitor.device_data["device1"]["sdcs"] == 2
    assert monitor.model_data["test_model.tflite"]["sdcs"] == 2
