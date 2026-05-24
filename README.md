# rad_experiment_monitoring_cli
Terminal tool to monitor radiation experiments (throwing radiation at computing devices and collecting SDCs (Single Data Corruption = wrong output values)

### Usage

python3 monitor.py --logs-folder LOGS_FOLDERPATH

### Expected log sctructure

logs/
├── rasp4-coral
│   ├── 2025_12_20_08_59_08_run_mobilenet_v2_coral_ECC_OFF_rasp4-coral.log
│   ├── 2025_12_20_13_52_00_run_base_vit_8_ECC_OFF_rasp4-coral.log
│   └── ...
├── device2
│   └── ...
└── device3
    └── ...