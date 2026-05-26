import pytest
from monitoring.parser import extract_model_name, parse_start_time, count_sdcs, find_last_sdc_timestamp

def test_extract_model_name():
    content = "#HEADER model=/path/to/my_model.tflite version=1.0"
    assert extract_model_name(content) == "my_model.tflite"
    
    content = "#HEADER other_field=value model=another_model.bin"
    assert extract_model_name(content) == "another_model.bin"
    
    content = "No header here"
    assert extract_model_name(content) == "Unknown Model"

def test_parse_start_time_server_begin():
    content = "#SERVER_BEGIN Y:2024 M:05 D:20 TIME:10:30:45"
    ts = parse_start_time(content)
    assert ts is not None
    # 2024-05-20 10:30:45 UTC might vary by local timezone if not careful, 
    # but the logic uses datetime.datetime which is naive by default.
    # Let's check relative values or components if possible, 
    # but for simplicity in this project's context, let's just ensure it parses.
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    assert dt.year == 2024
    assert dt.month == 5
    assert dt.day == 20
    assert dt.hour == 10
    assert dt.minute == 30
    assert dt.second == 45

def test_parse_start_time_begin():
    content = "#BEGIN Y:1970 M:01 D:15 Time:02:19:10"
    ts = parse_start_time(content)
    assert ts is not None
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    assert dt.year == 1970
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 2
    assert dt.minute == 19
    assert dt.second == 10

def test_parse_start_time_invalid():
    assert parse_start_time("Nothing here") is None
    assert parse_start_time("#BEGIN Y:2024 M:13 D:01 Time:10:00:00") is None # Invalid month

def test_count_sdcs():
    content = "SDC occurred\nsdc again\nNo error here\nThird SDC"
    assert count_sdcs(content) == 3
    assert count_sdcs("Clean log") == 0

def test_find_last_sdc_timestamp():
    start_ts = 1000000.0
    content = """
#BEGIN Y:1970 M:01 D:01 Time:00:00:00
AccTime:10.5
Some output
AccTime:20.0
SDC detected
AccTime:30.0
Normal output
"""
    # Last SDC is at AccTime 20.0
    assert find_last_sdc_timestamp(content, start_ts) == 1000000.0 + 20.0

def test_find_last_sdc_timestamp_multiple():
    start_ts = 0.0
    content = """
AccTime:10.0
SDC 1
AccTime:20.0
SDC 2
AccTime:30.0
Normal
"""
    assert find_last_sdc_timestamp(content, start_ts) == 20.0
def test_find_last_sdc_timestamp_no_sdc():
    assert find_last_sdc_timestamp("AccTime:10\nNormal", 0.0) is None

def test_find_last_sdc_timestamp_no_start_ts():
    content = "AccTime:10\nSDC"
    assert find_last_sdc_timestamp(content, None) is None
