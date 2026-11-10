import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr, field_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "https://litellm.dsai-sdia.ssc-spc.cloud-nuage.canada.ca/v1"


class Settings(BaseModel):
    key: SecretStr = SecretStr("")
    base: str = DEFAULT_BASE
    model: str = "auto"
    runs: int = Field(default=4, ge=3, le=4)
    timeout: float = Field(default=180, gt=0)

    @field_validator("base")
    @classmethod
    def secure_base(cls, value):
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query:
            raise ValueError("LLM_BASE must be an HTTPS base URL without credentials/query")
        return value.rstrip("/")

    @classmethod
    def load(cls, path=ROOT / ".env"):
        values = {**dotenv_values(path), **os.environ}
        return cls(
            **{
                field: values[key]
                for field, key in {
                    "key": "LLM_KEY",
                    "base": "LLM_BASE",
                    "model": "LLM_MODEL",
                    "runs": "STEP_GENERATION_RUNS",
                    "timeout": "LLM_TIMEOUT_SECONDS",
                }.items()
                if values.get(key) is not None
            }
        )

    def require_key(self):
        if not self.key.get_secret_value().strip():
            raise ValueError(f"Missing LLM_KEY. Paste it into {ROOT / '.env'}; never into chat.")
