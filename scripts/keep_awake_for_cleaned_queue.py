"""Temporary per-thread system-awake request covering all six authorized runs."""

import ctypes
import json
import sys
import time

from canadianness_eval.queued_cleaned import STATE

if sys.platform == "win32":
    set_state = ctypes.windll.kernel32.SetThreadExecutionState
    if not set_state(0x80000001):
        raise RuntimeError("Could not request temporary system-awake state")
    try:
        while not (STATE / "completion.json").exists():
            path = STATE / "supervision.jsonl"
            if path.exists():
                lines = path.read_text(encoding="utf8").splitlines()
                if lines and json.loads(lines[-1]).get("event") == "CLEANED_SUPERVISOR_STOPPED":
                    break
            time.sleep(600)
    finally:
        set_state(0x80000000)
