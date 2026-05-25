import os
from pathlib import Path
from threading import Lock
from .parser import extract_model_name, count_sdcs, read_log_delta, read_tail, parse_start_time, find_last_sdc_timestamp

class RadLogsMonitor:
    """Orchestrates the log parsing and data management."""
    
    def __init__(self, logs_folder):
        self.logs_path = Path(logs_folder)
        self.lock = Lock()
        self.device_data = {}   # {device_name: {"logs": set(), "sdcs": int, "latest_log": str, "last_update_time": float, "last_sdc_timestamp": float | None}}
        self.model_data = {}    # {model_name: {"logs": set(), "log_paths": set(), "sdcs": int, "last_update_time": float | None, "last_sdc_timestamp": float | None}}
        self.file_to_model = {} # {file_path_str: model_name}
        self.file_to_start_ts = {} # {file_path_str: start_timestamp}
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
        last_sdc_ts_overall = None
        log_names = {f.name for f in log_files}
        
        # Sort to find latest log for display
        sorted_logs = sorted(log_files, key=os.path.getmtime)
        latest_log_name = sorted_logs[-1].name if sorted_logs else "None"
        last_update_time = sorted_logs[-1].stat().st_mtime if sorted_logs else None

        for log_file in log_files:
            count, ts = self._process_single_log_initial(device_name, log_file)
            sdc_total += count
            if ts is not None:
                if last_sdc_ts_overall is None or ts > last_sdc_ts_overall:
                    last_sdc_ts_overall = ts

        self.device_data[device_name] = {
            "logs": log_names,
            "sdcs": sdc_total,
            "latest_log": latest_log_name,
            "last_update_time": last_update_time,
            "last_sdc_timestamp": last_sdc_ts_overall
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
                
                start_ts = parse_start_time(content)
                self.file_to_start_ts[file_str] = start_ts
                
                last_sdc_ts = find_last_sdc_timestamp(content, start_ts)
                
                mtime = log_file.stat().st_mtime
                self._update_model_stats(model_name, log_file, sdc_count, mtime, last_sdc_ts)
                return sdc_count, last_sdc_ts
        except Exception:
            return 0, None

    def _update_model_stats(self, model, log_path, sdc_delta, update_time=None, sdc_timestamp=None):
        if model not in self.model_data:
            self.model_data[model] = {
                "logs": set(),
                "log_paths": set(),
                "sdcs": 0,
                "last_update_time": None,
                "last_sdc_timestamp": None
            }
        self.model_data[model]["logs"].add(log_path.name)
        self.model_data[model]["log_paths"].add(log_path)
        self.model_data[model]["sdcs"] += sdc_delta
        
        if sdc_timestamp is not None:
            current_sdc = self.model_data[model]["last_sdc_timestamp"]
            if current_sdc is None or sdc_timestamp > current_sdc:
                self.model_data[model]["last_sdc_timestamp"] = sdc_timestamp

        if update_time is not None:
            current_last = self.model_data[model]["last_update_time"]
            if current_last is None or update_time > current_last:
                self.model_data[model]["last_update_time"] = update_time

    def _handle_log_update(self, file_path):
        device_name = file_path.parent.name
        file_str = str(file_path.resolve())

        with self.lock:
            self._ensure_device_registered(device_name, file_path.name)
            
            old_size = self.file_sizes.get(file_str, 0)
            new_content, current_size = read_log_delta(file_path, old_size)
            self.file_sizes[file_str] = current_size

            model_name = self._get_or_extract_model(file_str, file_path)

            if new_content or old_size == 0:
                sdc_delta = count_sdcs(new_content)
                self.device_data[device_name]["sdcs"] += sdc_delta
                
                start_ts = self.file_to_start_ts.get(file_str)
                last_sdc_ts = find_last_sdc_timestamp(new_content, start_ts)
                
                if last_sdc_ts is not None:
                    current_device_sdc = self.device_data[device_name].get("last_sdc_timestamp")
                    if current_device_sdc is None or last_sdc_ts > current_device_sdc:
                        self.device_data[device_name]["last_sdc_timestamp"] = last_sdc_ts

                self._update_model_stats(model_name, file_path, sdc_delta, update_time=None, sdc_timestamp=last_sdc_ts)
            
            try:
                mtime = file_path.stat().st_mtime
            except Exception:
                import time
                mtime = time.time()
                
            self.device_data[device_name]["last_update_time"] = mtime
            
            if model_name not in self.model_data:
                self.model_data[model_name] = {
                    "logs": set(),
                    "log_paths": set(),
                    "sdcs": 0,
                    "last_update_time": None,
                    "last_sdc_timestamp": None
                }
            self.model_data[model_name]["log_paths"].add(file_path)
            self.model_data[model_name]["logs"].add(file_path.name)
            current_last = self.model_data[model_name]["last_update_time"]
            if current_last is None or mtime > current_last:
                self.model_data[model_name]["last_update_time"] = mtime
            
            self.latest_lines = read_tail(file_path)

    def _ensure_device_registered(self, device_name, log_name):
        if device_name not in self.device_data:
            self.device_data[device_name] = {
                "logs": set(),
                "sdcs": 0,
                "latest_log": "",
                "last_update_time": None,
                "last_sdc_timestamp": None
            }
        self.device_data[device_name]["logs"].add(log_name)
        self.device_data[device_name]["latest_log"] = log_name

    def _get_or_extract_model(self, file_str, file_path):
        if file_str not in self.file_to_model:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    header = f.read(4096)
                    self.file_to_model[file_str] = extract_model_name(header)
                    self.file_to_start_ts[file_str] = parse_start_time(header)
            except Exception:
                self.file_to_model[file_str] = "Unknown Model"
        return self.file_to_model[file_str]

    def _initialize_tail_buffer(self):
        all_logs = list(self.logs_path.glob("*/*.log"))
        if all_logs:
            newest_overall = max(all_logs, key=os.path.getmtime)
            self.latest_lines = read_tail(newest_overall)
