"""Temporarily prevent automatic system sleep while the authorized queue runs."""

import ctypes
import json
import sys
import time

from canadianness_eval.queued_workbook import STATE

if sys.platform == "win32":
    # Per-thread execution request, released on exit; no power-plan settings change.
    set_state = ctypes.windll.kernel32.SetThreadExecutionState
    if not set_state(0x80000001):
        raise RuntimeError("Could not request temporary system-awake state")
    try:
        while not (STATE / "final_results/three_model_mixed_temperature_results.xlsx").exists():
            events = STATE / "supervision.jsonl"
            if events.exists():
                lines = events.read_text(encoding="utf8").splitlines()
                if lines and json.loads(lines[-1]).get("event") == "SUPERVISOR_STOPPED":
                    break
            time.sleep(600)
    finally:
        set_state(0x80000000)
