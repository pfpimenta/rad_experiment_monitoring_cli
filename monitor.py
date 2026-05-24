import argparse
import os
from pathlib import Path

def parse_logs(logs_folder):
    """
    Parses radiation experiment logs and prints a summary.
    """
    logs_path = Path(logs_folder)
    if not logs_path.exists() or not logs_path.is_dir():
        print(f"Error: Path '{logs_folder}' does not exist or is not a directory.")
        return

    print(f"Scanning logs in: {logs_path.resolve()}")
    print("=" * 60)
    
    device_summaries = []

    # Iterate through device directories
    # Sort to ensure consistent output
    for device_dir in sorted(logs_path.iterdir()):
        if device_dir.is_dir():
            device_name = device_dir.name
            log_files = list(device_dir.glob("*.log"))
            
            sdc_total = 0
            for log_file in log_files:
                try:
                    # We use errors='ignore' to handle potential non-utf8 characters in raw logs
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        # Basic heuristic: count occurrences of 'SDC'
                        # This can be refined based on the actual log format
                        content = f.read()
                        sdc_total += content.upper().count("SDC")
                except Exception as e:
                    print(f"Warning: Could not read {log_file.name}: {e}")

            device_summaries.append({
                "device": device_name,
                "logs": len(log_files),
                "sdcs": sdc_total
            })

    if not device_summaries:
        print("No device folders found in the specified logs folder.")
        return

    # Header
    print(f"{'Device Name':<25} | {'Log Files':<10} | {'SDCs Found':<10}")
    print("-" * 60)
    
    total_logs = 0
    total_sdcs = 0

    for summary in device_summaries:
        print(f"{summary['device']:<25} | {summary['logs']:<10} | {summary['sdcs']:<10}")
        total_logs += summary['logs']
        total_sdcs += summary['sdcs']

    print("-" * 60)
    print(f"{'TOTAL':<25} | {total_logs:<10} | {total_sdcs:<10}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description="Monitor radiation experiment logs for SDCs."
    )
    parser.add_argument(
        "--logs-folder", 
        required=True, 
        help="Path to the root logs directory containing device subfolders."
    )
    
    args = parser.parse_args()
    parse_logs(args.logs_folder)

if __name__ == "__main__":
    main()
