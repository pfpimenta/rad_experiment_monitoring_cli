# rad_experiment_monitoring_cli
Terminal tool to monitor radiation experiments (throwing radiation at computing devices and collecting SDCs (Single Data Corruption = wrong output values).

The monitoring dashboard provides:
1. **Device Overview**: Summary of logs and total SDCs per device folder.
2. **Benchmark Logs**: Detailed breakdown of logs and SDCs per benchmark.
3. **Live Active Log Output**: Real-time view of the most recent log activity with highlighted SDC events.

### Installation

You can install the tool globally (or in a virtual environment) using:

```bash
pip install .
```

This will make the `rad-monitor` command available in your terminal.

### Usage

After installation, you can run the monitor using:

```bash
rad-monitor --logs-folder LOGS_FOLDERPATH [--cooldown SECONDS]
```

Or run it directly with python:

```bash
python3 monitor.py --logs-folder LOGS_FOLDERPATH [--cooldown SECONDS]
```

*   `--logs-folder`: Path to the root logs directory.
*   `--cooldown`: (Optional) Cool down period between processing log updates in seconds. Defaults to `1.0`.

Example:

```bash
rad-monitor --logs-folder test_logs/
```

### Expected log sctructure

```text
logs/
├── rasp4-coral
│   ├── 1970_12_20_08_59_08_run_mobilenet_v2_coral_ECC_OFF_rasp4-coral.log
│   ├── 1970_12_20_13_52_00_run_base_vit_8_ECC_OFF_rasp4-coral.log
│   └── ...
├── other_device
│   └── ...
└── ...
    └── ...
```

### TODOs
* Automated Testing: Add a tests/ directory with unit tests for the regex extraction and integration tests using pytest to simulate log file updates.