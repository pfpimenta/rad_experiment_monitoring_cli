import os
import re

import datetime

def extract_model_name(content: str) -> str:
    """Extracts the model filename from the #HEADER line."""
    match = re.search(r'#HEADER.*model=([^ \n\r]+)', content)
    if match:
        model_path = match.group(1)
        return os.path.basename(model_path)
    return "Unknown Model"

def parse_start_time(content: str) -> float | None:
    """Parses the absolute start time from #SERVER_BEGIN or #BEGIN."""
    # Try #SERVER_BEGIN first
    match = re.search(r'#SERVER_BEGIN Y:(\d+) M:(\d+) D:(\d+) TIME:(\d+):(\d+):(\d+)', content)
    if not match:
        # Try #BEGIN
        match = re.search(r'#BEGIN Y:(\d+) M:(\d+) D:(\d+) Time:(\d+):(\d+):(\d+)', content)
    
    if match:
        try:
            dt = datetime.datetime(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
                hour=int(match.group(4)),
                minute=int(match.group(5)),
                second=int(match.group(6))
            )
            return dt.timestamp()
        except ValueError:
            pass
    return None

def count_sdcs(content: str) -> int:
    """Counts the number of SDC occurrences in the given content."""
    return content.upper().count("SDC")

def find_last_sdc_timestamp(content: str, start_ts: float | None) -> float | None:
    """Finds the timestamp of the last SDC in the content."""
    if "SDC" not in content.upper():
        return None
    
    # Split by lines and look for SDC backwards
    lines = content.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if "SDC" in lines[i].upper():
            # Found SDC, now look for the nearest AccTime BEFORE it
            for j in range(i, -1, -1):
                match = re.search(r'AccTime:\s*([\d.]+)', lines[j])
                if match:
                    acc_time = float(match.group(1))
                    if start_ts is not None:
                        return start_ts + acc_time
                    return None # Cannot calculate absolute without start_ts
    return None

def read_log_delta(file_path, old_size):
    """Reads the newly appended content from a log file."""
    current_size = file_path.stat().st_size
    if current_size <= old_size:
        return "", current_size

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(old_size)
            new_content = f.read()
            return new_content, current_size
    except Exception:
        return "", old_size

def read_tail(file_path, line_count=12):
    """Reads the last few lines of a file for display."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-line_count:]]
    except Exception:
        return []
