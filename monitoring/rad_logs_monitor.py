import os
from pathlib import Path
from threading import Lock
from .parser import extract_model_name, count_sdcs, read_log_delta, read_tail

class RadLogsMonitor:
    """Orchestrates the log parsing and data management."""
    
    def __init__(self, logs_folder):
        self.logs_path = Path(logs_folder)
        self.lock = Lock()
        self.device_data = {}   # {device_name: {"logs": set(), "sdcs": int, "latest_log": str, "last_update_time": float}}
        self.model_data = {}    # {(device, model): {"logs": set(), "sdcs": int}}
        self.file_to_model = {} # {file_path_str: model_name}
        self.file_sizes = {}    # {file_path_str: last_read_size}
        self.latest_lines = []
        self.pending_files = set()

    def queue_update(self, file_path):
        """Thread-safe queuing of file updates."""
        with self.lock:
            self.pending_files.add(file_path)

    def process_updates(self):
        """Drains the update queue and processes each file."""
        with self.lock:
            to_process = list(self.pending_files)
            self.pending_files.clear()
        
        for file_path in to_process:
            self._handle_log_update(file_path)

    def initial_scan(self):
        """Performs a full scan of the logs directory on startup."""
        with self.lock:
            for device_dir in sorted(self.logs_path.iterdir()):
                if device_dir.is_dir():
                    self._scan_device_folder(device_dir)
            
            self._initialize_tail_buffer()

    def _scan_device_folder(self, device_dir):
        device_name = device_dir.name
        log_files = list(device_dir.glob("*.log"))
        
        sdc_total = 0
        log_names = {f.name for f in log_files}
        
        # Sort to find latest log for display
        sorted_logs = sorted(log_files, key=os.path.getmtime)
        latest_log_name = sorted_logs[-1].name if sorted_logs else "None"
        last_update_time = sorted_logs[-1].stat().st_mtime if sorted_logs else None

        for log_file in log_files:
            sdc_total += self._process_single_log_initial(device_name, log_file)

        self.device_data[device_name] = {
            "logs": log_names,
            "sdcs": sdc_total,
            "latest_log": latest_log_name,
            "last_update_time": last_update_time
        }

    def _process_single_log_initial(self, device_name, log_file):
        file_str = str(log_file.resolve())
        self.file_sizes[file_str] = log_file.stat().st_size
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                sdc_count = count_sdcs(content)
                
                model_name = extract_model_name(content)
                self.file_to_model[file_str] = model_name
                self._update_model_stats(device_name, model_name, log_file.name, sdc_count)
                return sdc_count
        except Exception:
            return 0

    def _update_model_stats(self, device, model, log_name, sdc_delta):
        key = (device, model)
        if key not in self.model_data:
            self.model_data[key] = {"logs": set(), "sdcs": 0}
        self.model_data[key]["logs"].add(log_name)
        self.model_data[key]["sdcs"] += sdc_delta

    def _handle_log_update(self, file_path):
        device_name = file_path.parent.name
        file_str = str(file_path.resolve())

        with self.lock:
            self._ensure_device_registered(device_name, file_path.name)
            
            old_size = self.file_sizes.get(file_str, 0)
            new_content, current_size = read_log_delta(file_path, old_size)
            self.file_sizes[file_str] = current_size

            if new_content or old_size == 0:
                sdc_delta = count_sdcs(new_content)
                self.device_data[device_name]["sdcs"] += sdc_delta
                
                model_name = self._get_or_extract_model(file_str, file_path)
                self._update_model_stats(device_name, model_name, file_path.name, sdc_delta)
            
            try:
                self.device_data[device_name]["last_update_time"] = file_path.stat().st_mtime
            except Exception:
                import time
                self.device_data[device_name]["last_update_time"] = time.time()
            
            self.latest_lines = read_tail(file_path)

    def _ensure_device_registered(self, device_name, log_name):
        if device_name not in self.device_data:
            self.device_data[device_name] = {
                "logs": set(),
                "sdcs": 0,
                "latest_log": "",
                "last_update_time": None
            }
        self.device_data[device_name]["logs"].add(log_name)
        self.device_data[device_name]["latest_log"] = log_name

    def _get_or_extract_model(self, file_str, file_path):
        if file_str not in self.file_to_model:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    header = f.read(4096)
                    self.file_to_model[file_str] = extract_model_name(header)
            except Exception:
                self.file_to_model[file_str] = "Unknown Model"
        return self.file_to_model[file_str]

    def _initialize_tail_buffer(self):
        all_logs = list(self.logs_path.glob("*/*.log"))
        if all_logs:
            newest_overall = max(all_logs, key=os.path.getmtime)
            self.latest_lines = read_tail(newest_overall)
