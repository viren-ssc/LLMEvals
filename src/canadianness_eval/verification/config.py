import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field

from .models import Record


class Config(Record):
    database: Path = Path("outputs/verification/pipeline.sqlite3")
    cache: Path = Path("outputs/verification/sources")
    workers: int = Field(default=4, ge=1, le=32)
    attempts: int = Field(default=3, ge=1, le=10)
    source_ttl_hours: int = Field(default=24, ge=1)
    contact: str = "CanadianBenchmarkVerifier/1.0"
    extra_authority_hosts: list[str] = Field(default_factory=list)
    source_timeout: float = Field(default=20, gt=0)
    discovery_index: Path | None = None

    @classmethod
    def load(cls):
        v = {**dotenv_values(".env"), **os.environ}
        mapping = {
            "database": "VERIFY_DB",
            "cache": "VERIFY_CACHE",
            "workers": "VERIFY_WORKERS",
            "contact": "VERIFY_USER_AGENT",
            "source_timeout": "VERIFY_SOURCE_TIMEOUT",
            "discovery_index": "VERIFY_DISCOVERY_INDEX",
        }
        args = {k: v[n] for k, n in mapping.items() if v.get(n)}
        if v.get("VERIFY_AUTHORITY_HOSTS"):
            args["extra_authority_hosts"] = v["VERIFY_AUTHORITY_HOSTS"].split(",")
        return cls(**args)
