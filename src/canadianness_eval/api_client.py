"""Only this module transmits data. TLS verification and sequential bounded retries."""

import json
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from pydantic import BaseModel, ValidationError

from .model_discovery import select_model

log = logging.getLogger(__name__)


class GatewayError(RuntimeError):
    pass


class Gateway:
    def __init__(self, settings, transport=None, sleep=time.sleep):
        settings.require_key()
        self.settings = settings
        self.client = httpx.Client(
            base_url=settings.base + "/",
            timeout=settings.timeout,
            verify=True,
            follow_redirects=False,
            transport=transport,
            headers={"Authorization": "Bearer " + settings.key.get_secret_value()},
        )
        self.sleep = sleep
        self.model_id = None
        self.structured_mode = "json_schema"
        self.attempts = 0
        self.history = []
        self.auth_failed = False

    def close(self):
        self.client.close()

    def safe_error(self, exc):
        if isinstance(exc, (GatewayError, ValueError)):
            return str(exc).replace(self.settings.key.get_secret_value(), "[REDACTED]")
        return type(exc).__name__

    def request(self, method, path, **kwargs):
        if self.auth_failed:
            raise GatewayError(
                "Authentication previously failed; fix credentials before retrying this run"
            )
        for attempt in range(3):
            self.attempts += 1
            start = time.perf_counter()
            audit = {"method": method, "path": path}
            audit["request_timestamp"] = datetime.now(UTC).isoformat()
            if "json" in kwargs:
                audit["request_body"] = kwargs["json"]
            response = None
            try:
                response = self.client.request(method, path, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError):
                self.history.append(
                    {
                        **audit,
                        "status": "network_or_timeout",
                        "latency": time.perf_counter() - start,
                    }
                )
                if attempt == 2:
                    raise GatewayError(
                        "Network/timeout failure; check connectivity, VPN and gateway access"
                    ) from None
            else:
                self.history.append(
                    {
                        **audit,
                        "status": response.status_code,
                        "latency": time.perf_counter() - start,
                    }
                )
                if response.status_code in (401, 403):
                    self.auth_failed = True
                    raise GatewayError(
                        f"HTTP {response.status_code}: key invalid, expired or access denied"
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    if response.headers.get("retry-after"):
                        self.history[-1]["retry_after"] = response.headers["retry-after"]
                    if attempt == 2:
                        raise GatewayError(
                            f"HTTP {response.status_code}: transient retries exhausted"
                        )
                else:
                    return response
            delay = 2**attempt
            if response is not None and response.status_code == 429:
                retry_after = response.headers.get("retry-after", "")
                try:
                    requested = float(retry_after)
                except ValueError:
                    try:
                        requested = (
                            parsedate_to_datetime(retry_after) - datetime.now(UTC)
                        ).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        requested = 0
                if requested > 60:
                    raise GatewayError(
                        "Rate limit requests a wait over 60 seconds; checkpoint and resume later"
                    )
                delay = max(delay, requested)
            self.history[-1]["retry_delay_seconds"] = delay
            self.sleep(delay)

    def discover(self):
        r = self.request("GET", "models")
        if r.status_code != 200:
            raise GatewayError(f"Model discovery HTTP {r.status_code}")
        try:
            ids = [x["id"] for x in r.json()["data"]]
            if not all(isinstance(x, str) for x in ids):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise GatewayError("Invalid /models response") from None
        self.model_id = select_model(ids, self.settings.model)
        return ids

    def generate(self, prompt, schema: type[BaseModel] | None = None):
        if not self.model_id:
            raise GatewayError("Discover and resolve the judge before generation")
        errors = []
        for validation_attempt in range(3):
            body = {"model": self.model_id, "messages": [{"role": "user", "content": prompt}]}
            if schema:
                spec = schema.model_json_schema()
                body["messages"][0]["content"] += (
                    "\nReturn only JSON matching this schema:\n" + json.dumps(spec)
                )
                if self.structured_mode == "json_schema":
                    body["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {"name": schema.__name__, "schema": spec, "strict": True},
                    }
            r = self.request("POST", "chat/completions", json=body)
            self.history[-1]["request_body"] = body
            # Switch only for explicit parameter/schema support errors, never auth/server errors.
            if r.status_code in (400, 422) and "response_format" in body:
                try:
                    error = json.dumps(r.json().get("error", {})).lower()
                except ValueError:
                    error = ""
                if any(
                    word in error
                    for word in ("response_format", "json_schema", "structured", "schema")
                ):
                    self.structured_mode = "validated_json"
                    continue
            if r.status_code != 200:
                raise GatewayError(f"Chat completion HTTP {r.status_code}")
            try:
                payload = r.json()
                self.history[-1].update(raw_response=payload)
                raw = payload["choices"][0]["message"]["content"]
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError("empty content")
                self.history[-1].update(
                    {"raw_response": payload, "validation_attempt": validation_attempt + 1}
                )
                if schema is None:
                    return raw
                return parse_structured(raw, schema)
            except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
                errors.append(type(exc).__name__)
                log.warning(
                    "Structured/response validation failed (%s), attempt %d",
                    type(exc).__name__,
                    validation_attempt + 1,
                )
        raise GatewayError(
            "Invalid/empty structured output after bounded attempts: " + ", ".join(errors)
        )


def parse_structured(raw, schema):
    value = raw.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return schema.model_validate_json(value)
