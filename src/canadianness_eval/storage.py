import hashlib
import json
import os
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import yaml


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def versions():
    return {p: version(p) for p in ["deepeval", "pydantic", "httpx", "pandas", "openpyxl"]}
