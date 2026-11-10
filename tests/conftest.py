import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import httpx
import pytest

import canadianness_eval  # noqa: F401
from canadianness_eval.api_client import Gateway
from canadianness_eval.settings import Settings


@pytest.fixture
def gateway_factory():
    gateways = []

    def factory(handler):
        gateway = Gateway(
            Settings(key="test-secret"),
            transport=httpx.MockTransport(handler),
            sleep=lambda _: None,
        )
        gateway.model_id = "gpt-oss-120b"
        gateways.append(gateway)
        return gateway

    yield factory
    for gateway in gateways:
        gateway.close()
