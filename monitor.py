import argparse
import os
import time
import re
from pathlib import Path
from threading import Lock
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogChangeHandler(FileSystemEventHandler):
    """Listens for file updates and recalculates SDC deltas on the fly."""
    def __init__(self, monitor):
        self.monitor = monitor

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.monitor.handle_log_update(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.monitor.handle_log_update(Path(event.src_path))


class RadiationMonitor:
    def __init__(self, logs_folder):
        self.logs_path = Path(logs_folder)
        self.lock = Lock()  # Prevents race conditions between initial scan and watchdog
        self.device_data = {}  # Format: {device_name: {"logs": set(), "sdcs": int, "latest_log": str}}
        self.model_data = {}   # Format: {(device, model): {"logs": set(), "sdcs": int}}
        self.file_to_model = {} # Tracks {file_path_str: model_name}
        self.file_sizes = {}   # Tracks file size to only read *new* lines
        self.latest_lines = [] # Stores the last few lines of the active log

    def _extract_model(self, content):
        """Extracts the model filename from the #HEADER line."""
        match = re.search(r'#HEADER.*model=([^ ]+)', content)
        if match:
            model_path = match.group(1)
            return os.path.basename(model_path)
        return "Unknown Model"

    def initial_scan(self):
        """Performs the baseline scan of the directory structure."""
        with self.lock:
            for device_dir in sorted(self.logs_path.iterdir()):
                if device_dir.is_dir():
                    device_name = device_dir.name
                    log_files = list(device_dir.glob("*.log"))
                    
                    sdc_total = 0
                    log_names = set()
                    
                    # Sort to find the newest active file
                    sorted_logs = sorted(log_files, key=os.path.getmtime)
                    latest_log_name = sorted_logs[-1].name if sorted_logs else "None"

                    for log_file in log_files:
                        log_names.add(log_file.name)
                        file_str = str(log_file.resolve())
                        try:
                            # Save current size so we only read append deltas later
                            self.file_sizes[file_str] = log_file.stat().st_size
                            
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                sdc_count = content.upper().count("SDC")
                                sdc_total += sdc_count
                                
                                # Extract model and update model_data
                                model_name = self._extract_model(content)
                                self.file_to_model[file_str] = model_name
                                key = (device_name, model_name)
                                if key not in self.model_data:
                                    self.model_data[key] = {"logs": set(), "sdcs": 0}
                                self.model_data[key]["logs"].add(log_file.name)
                                self.model_data[key]["sdcs"] += sdc_count
                        except Exception:
                            pass

                    self.device_data[device_name] = {
                        "logs": log_names,
                        "sdcs": sdc_total,
                        "latest_log": latest_log_name
                    }
            
            # Populate initial tail view with the absolute newest log overall
            all_logs = list(self.logs_path.glob("*/*.log"))
            if all_logs:
                newest_overall = max(all_logs, key=os.path.getmtime)
                self._update_tail_buffer(newest_overall)

    def handle_log_update(self, file_path):
        """Triggered by watchdog when a log file changes."""
        device_name = file_path.parent.name
        file_str = str(file_path.resolve())

        with self.lock:
            if device_name not in self.device_data:
                self.device_data[device_name] = {"logs": set(), "sdcs": 0, "latest_log": ""}

            # Register log file if it's brand new
            if file_path.name not in self.device_data[device_name]["logs"]:
                self.device_data[device_name]["logs"].add(file_path.name)
            
            self.device_data[device_name]["latest_log"] = file_path.name

            # Efficient Delta-Reading: Only parse the newly appended bytes
            old_size = self.file_sizes.get(file_str, 0)
            try:
                current_size = file_path.stat().st_size
                self.file_sizes[file_str] = current_size

                if current_size > old_size or old_size == 0:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        if old_size > 0:
                            f.seek(old_size)
                            new_content = f.read()
                        else:
                            new_content = f.read()
                        
                        sdc_delta = new_content.upper().count("SDC")
                        self.device_data[device_name]["sdcs"] += sdc_delta
                        
                        # Ensure model mapping exists
                        if file_str not in self.file_to_model:
                            # Re-read from start if model is not known (to find #HEADER)
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f2:
                                header_content = f2.read(4096) # Header is usually at the start
                                self.file_to_model[file_str] = self._extract_model(header_content)
                        
                        model_name = self.file_to_model[file_str]
                        key = (device_name, model_name)
                        if key not in self.model_data:
                            self.model_data[key] = {"logs": set(), "sdcs": 0}
                        self.model_data[key]["logs"].add(file_path.name)
                        self.model_data[key]["sdcs"] += sdc_delta
                
                # Update the tail panel buffer
                self._update_tail_buffer(file_path)
            except Exception:
                pass

    def _update_tail_buffer(self, file_path):
        """Keeps the tail buffer loaded with the freshest terminal data."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                self.latest_lines = [line.strip() for line in lines[-12:]]
        except Exception:
            pass

    def generate_layout(self) -> Layout:
        """Draws the dynamic split panel dashboard layout."""
        layout = Layout()
        layout.split_row(
            Layout(name="table_pane", ratio=3),
            Layout(name="tail_pane", ratio=2)
        )
        
        layout["table_pane"].split_column(
            Layout(name="device_summary"),
            Layout(name="model_summary")
        )

        # 1. Device Summary Table
        device_table = Table(show_header=True, header_style="bold cyan", expand=True)
        device_table.add_column("Device Name", style="bold white")
        device_table.add_column("Log Files", justify="right")
        device_table.add_column("SDCs Found", justify="right")

        total_logs = 0
        total_sdcs = 0

        with self.lock:
            for device, info in sorted(self.device_data.items()):
                num_logs = len(info["logs"])
                sdc_count = info["sdcs"]
                total_logs += num_logs
                total_sdcs += sdc_count
                sdc_style = "bold red" if sdc_count > 0 else "green"
                device_table.add_row(device, str(num_logs), f"[{sdc_style}]{sdc_count}[/{sdc_style}]")

            device_table.add_section() 
            device_table.add_row("TOTAL", str(total_logs), f"[bold magenta]{total_sdcs}[/bold magenta]")

        layout["device_summary"].update(Panel(device_table, title="Device Overview", border_style="blue"))

        # 2. Model Summary Table
        model_table = Table(show_header=True, header_style="bold yellow", expand=True)
        model_table.add_column("Device", style="dim white")
        model_table.add_column("Model Name", style="bold white")
        model_table.add_column("Logs", justify="right")
        model_table.add_column("SDCs", justify="right")

        with self.lock:
            for (device, model), info in sorted(self.model_data.items()):
                num_logs = len(info["logs"])
                sdc_count = info["sdcs"]
                sdc_style = "bold red" if sdc_count > 0 else "green"
                model_table.add_row(device, model, str(num_logs), f"[{sdc_style}]{sdc_count}[/{sdc_style}]")

        layout["model_summary"].update(Panel(model_table, title="Model-wise breakdown", border_style="yellow"))

        # 3. Real-time Tail Panel Generation
        tail_text = "\n".join(self.latest_lines) if self.latest_lines else "Waiting for log events..."
        tail_text = tail_text.replace("SDC", "[bold blink red]SDC[/bold blink red]")
        tail_text = tail_text.replace("sdc", "[bold blink red]sdc[/bold blink red]")

        layout["tail_pane"].update(Panel(tail_text, title="Live Active Log Output", border_style="green"))

        return layout


def main():
    parser = argparse.ArgumentParser(description="Monitor radiation experiment logs for SDCs.")
    parser.add_argument("--logs-folder", required=True, help="Path to the root logs directory.")
    args = parser.parse_args()

    logs_path = Path(args.logs_folder)
    if not logs_path.exists() or not logs_path.is_dir():
        print(f"Error: Path '{args.logs_folder}' does not exist or is not a directory.")
        return

    console = Console()
    monitor = RadiationMonitor(args.logs_folder)
    
    console.print("[yellow]Running initial baseline log parse...[/yellow]")
    monitor.initial_scan()
    console.print("[green]Baseline complete. Starting real-time observer thread...[/green]")
    time.sleep(0.5)

    # Initialize Watchdog Observer thread
    event_handler = LogChangeHandler(monitor)
    observer = Observer()
    observer.schedule(event_handler, path=str(logs_path.resolve()), recursive=True)
    observer.start()

    # Enter the Rich Live update loop context manager
    with Live(monitor.generate_layout(), screen=True, auto_refresh=True, refresh_per_second=4) as live:
        try:
            while True:
                # We update the layout instance directly, watchdog manages data states
                live.update(monitor.generate_layout())
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            observer.stop()
            observer.join()

if __name__ == "__main__":
    main()