"""Explicit opt-in only: never sends test data merely because a key is present."""

import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to authorize remote smoke test",
)
def test_live_connection():
    from canadianness_eval.cli import connect
    from canadianness_eval.settings import Settings

    gateway = connect(Settings.load())
    gateway.close()
