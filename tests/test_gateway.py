import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from canadianness_eval.api_client import GatewayError, parse_structured
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.model_discovery import select_model
from canadianness_eval.settings import DEFAULT_BASE, Settings


class Answer(BaseModel):
    answer: str


def completion(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_settings(tmp_path, monkeypatch):
    for key in ("LLM_KEY", "LLM_BASE", "LLM_MODEL", "STEP_GENERATION_RUNS", "LLM_TIMEOUT_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text("LLM_KEY=test-secret\n")
    settings = Settings.load(path)
    assert settings.base == DEFAULT_BASE and settings.runs == 4 and settings.model == "auto"
    assert "test-secret" not in repr(settings)
    with pytest.raises(ValueError):
        Settings().require_key()
    with pytest.raises(ValueError):
        Settings(base="http://example.com")


@pytest.mark.parametrize(
    "model", ["gpt-oss-120b", "team/GPT_OSS_120B-prod", "deployment/gpt.oss.120b"]
)
def test_discovery_alias(model):
    assert select_model(["other", model]) == model


def test_ambiguous_and_explicit():
    with pytest.raises(ValueError):
        select_model(["gpt-oss-20b"])
    with pytest.raises(ValueError):
        select_model(["gpt-oss-120b", "team/gpt-oss-120b"])
    assert select_model(["deployment-17"], "deployment-17") == "deployment-17"


@pytest.mark.parametrize("status,attempts", [(401, 1), (403, 1), (429, 3), (500, 3), (503, 3)])
def test_retry_bounds(gateway_factory, status, attempts):
    gateway = gateway_factory(
        lambda _: httpx.Response(status, json={"error": "secret must not be shown"})
    )
    with pytest.raises(GatewayError) as caught:
        gateway.generate("test")
    assert gateway.attempts == attempts
    assert "secret must not" not in str(caught.value)


def test_network_retry(gateway_factory):
    def handler(request):
        raise httpx.ConnectError("private diagnostics", request=request)

    gateway = gateway_factory(handler)
    with pytest.raises(GatewayError, match="Network"):
        gateway.generate("test")
    assert gateway.attempts == 3


def test_structured_fallback(gateway_factory):
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(
                400, json={"error": {"message": "response_format json_schema unsupported"}}
            )
        return completion('{"answer":"Winnipeg"}')

    gateway = gateway_factory(handler)
    assert gateway.generate("capital", Answer).answer == "Winnipeg"
    assert gateway.structured_mode == "validated_json" and len(bodies) == 2
    assert "response_format" not in bodies[-1]


def test_structured_malformed_then_success(gateway_factory):
    replies = iter(["bad JSON", '{"wrong":2}', '```json\n{"answer":"Winnipeg"}\n```'])
    gateway = gateway_factory(lambda _: completion(next(replies)))
    assert gateway.generate("test", Answer).answer == "Winnipeg"
    assert gateway.attempts == 3


def test_empty_response_fails(gateway_factory):
    gateway = gateway_factory(lambda _: completion(""))
    with pytest.raises(GatewayError):
        gateway.generate("test")
    assert gateway.attempts == 3


def test_adapter_sync_async(gateway_factory):
    judge = RemoteJudge(gateway_factory(lambda _: completion('{"answer":"Winnipeg"}')))
    assert judge.generate("test", Answer).answer == "Winnipeg"
    assert asyncio.run(judge.a_generate("test", Answer)).answer == "Winnipeg"
    assert judge.get_model_name() == "gpt-oss-120b"


def test_parse_schema():
    assert parse_structured('{"answer":"ok"}', Answer).answer == "ok"
    with pytest.raises(ValueError):
        parse_structured('{"answer":null}', Answer)
