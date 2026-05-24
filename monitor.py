import argparse
import time
from pathlib import Path
from rich.console import Console
from rich.live import Live
from watchdog.observers import Observer

from monitoring.rad_logs_monitor import RadLogsMonitor
from monitoring.dashboard import Dashboard
from monitoring.watcher import LogChangeHandler

def parse_arguments():
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="Monitor radiation experiment logs for SDCs.")
    parser.add_argument("--logs-folder", required=True, help="Path to the root logs directory.")
    parser.add_argument("--cooldown", type=float, default=1.0, 
                        help="Cool down period between scans in seconds (default: 1.0).")
    return parser.parse_args()

def run_monitor(args):
    """Initializes and runs the monitoring loop."""
    logs_path = Path(args.logs_folder)
    if not logs_path.exists() or not logs_path.is_dir():
        print(f"Error: Path '{args.logs_folder}' does not exist or is not a directory.")
        return

    console = Console()
    monitor = RadLogsMonitor(args.logs_folder)
    
    console.print("[yellow]Running initial baseline log parse...[/yellow]")
    monitor.initial_scan()
    console.print("[green]Baseline complete. Starting real-time observer...[/green]")
    time.sleep(0.5)

    # Setup Watchdog
    event_handler = LogChangeHandler(monitor)
    observer = Observer()
    observer.schedule(event_handler, path=str(logs_path.resolve()), recursive=True)
    observer.start()

    try:
        with Live(Dashboard.generate(monitor.device_data, monitor.model_data, monitor.latest_lines), 
                  screen=True, auto_refresh=True, refresh_per_second=4) as live:
            while True:
                monitor.process_updates()
                live.update(Dashboard.generate(monitor.device_data, monitor.model_data, monitor.latest_lines))
                time.sleep(args.cooldown)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

def main():
    args = parse_arguments()
    run_monitor(args)

if __name__ == "__main__":
    main()
