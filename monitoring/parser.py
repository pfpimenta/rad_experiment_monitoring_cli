import os
import re

def extract_model_name(content: str) -> str:
    """Extracts the model filename from the #HEADER line."""
    match = re.search(r'#HEADER.*model=([^ ]+)', content)
    if match:
        model_path = match.group(1)
        return os.path.basename(model_path)
    return "Unknown Model"

def count_sdcs(content: str) -> int:
    """Counts the number of SDC occurrences in the given content."""
    return content.upper().count("SDC")

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
