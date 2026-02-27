# utils/heartbeat.py
# Heartbeat system for tracking daily execution status

import json
from pathlib import Path
from datetime import datetime

HEARTBEAT_FILE = Path("Output/heartbeat/last_run.json")

def write_heartbeat(status: str, events_processed: int, assets_data: dict):
    """
    Write heartbeat file after each run.
    
    Args:
        status: "SUCCESS" or "FAILED"
        events_processed: Number of events processed
        assets_data: Dict with snapshot info per asset
    """
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    heartbeat = {
        "last_run": datetime.now().isoformat(),
        "status": status,
        "events_processed": events_processed,
        "assets": assets_data
    }
    
    with open(HEARTBEAT_FILE, 'w') as f:
        json.dump(heartbeat, f, indent=2)
    
    print(f"[HEARTBEAT] Written: {HEARTBEAT_FILE}")

def read_heartbeat():
    """Read last heartbeat. Returns empty dict if not found."""
    if not HEARTBEAT_FILE.exists():
        return {}
    
    with open(HEARTBEAT_FILE, 'r') as f:
        return json.load(f)
