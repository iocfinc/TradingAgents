import os
from json import JSONDecodeError

import pytest
from langchain_openai import ChatOpenAI

from tradingagents.default_config import get_default_agent_model_map
from tradingagents.graph.trading_graph import build_role_llm_specs, resolve_agent_model_map
from tradingagents.llm_clients.factory import (
    create_llm_client,
    get_provider_definition,
    resolve_provider_bundle,
)


def test_resolve_agent_model_map_merges_partial_overrides() -> None:
    mapping = resolve_agent_model_map(
        {
            "llm_provider": "openai",
            "agent_model_map": {
                "market": "gpt-5.4-mini",
                "research_manager": "gpt-5.4",
            }
        }
    )

    assert mapping["market"] == "gpt-5.4-mini"
    assert mapping["research_manager"] == "gpt-5.4"
    assert mapping["trader"] == "gpt-5.4"
    assert mapping["risk_reflection"] == "gpt-5.4-mini"


def test_default_openrouter_map_prefers_deepseek_and_kimi() -> None:
    mapping = get_default_agent_model_map("openrouter")

    assert mapping["market"] == "tencent/hy3-preview"
    assert mapping["risk_reflection"] == "tencent/hy3-preview"
    assert mapping["portfolio_manager"] == "tencent/hy3-preview"


def test_resolve_agent_model_map_applies_quick_and_deep_selections() -> None:
    mapping = resolve_agent_model_map(
        {
            "llm_provider": "openrouter",
            "quick_think_llm": "tencent/hy3-preview",
            "deep_think_llm": "tencent/hy3-preview",
        }
    )

    assert mapping["market"] == "tencent/hy3-preview"
    assert mapping["social"] == "tencent/hy3-preview"
    assert mapping["bull_researcher"] == "tencent/hy3-preview"
    assert mapping["portfolio_manager"] == "tencent/hy3-preview"
    assert mapping["risk_reflection"] == "tencent/hy3-preview"


def test_build_role_llm_specs_use_explicit_models_without_route_llm() -> None:
    specs = build_role_llm_specs(
        {
            "llm_provider": "abacus",
            "provider_bundle_override": {
                "base_url": "https://workspace.abacus.ai/v1",
                "api_key_env": "ABACUS_API_KEY",
            },
            "agent_model_map": {
                "market": "gpt-5.4-mini",
                "social": "gpt-5.4-mini",
                "news": "gpt-5.4-mini",
                "fundamentals": "gpt-5.4-mini",
                "risk_reflection": "gpt-5.4-mini",
                "bull_researcher": "gpt-5.4",
                "bear_researcher": "gpt-5.4",
                "research_manager": "gpt-5.4",
                "trader": "gpt-5.4",
                "portfolio_manager": "gpt-5.4",
            },
        },
        extra_kwargs={"reasoning_effort": "medium"},
    )

    assert specs["market"]["model"] == "gpt-5.4-mini"
    assert specs["trader"]["model"] == "gpt-5.4"
    assert specs["portfolio_manager"]["provider_bundle"]["base_url"] == "https://workspace.abacus.ai/v1"
    assert specs["portfolio_manager"]["provider_bundle"]["api_key_env"] == "ABACUS_API_KEY"
    assert all(spec["model"] != "route-llm" for spec in specs.values())


def test_build_role_llm_specs_default_openrouter_models_avoid_gpt_fallback() -> None:
    specs = build_role_llm_specs({"llm_provider": "openrouter"})

    assert specs["market"]["model"] == "tencent/hy3-preview"
    assert specs["risk_reflection"]["model"] == "tencent/hy3-preview"
    assert specs["research_manager"]["model"] == "tencent/hy3-preview"


def test_abacus_provider_uses_openai_compatible_base_url_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("ABACUS_API_KEY", "abacus-test-key")
    monkeypatch.setattr(
        "tradingagents.llm_clients.openai_client.NormalizedChatOpenAI",
        FakeChatOpenAI,
    )

    client = create_llm_client(provider="abacus", model="gpt-5.4")
    llm = client.get_llm()

    assert isinstance(llm, FakeChatOpenAI)
    assert captured["model"] == "gpt-5.4"
    assert captured["base_url"] == "https://routellm.abacus.ai/v1"
    assert captured["api_key"] == "abacus-test-key"
    assert "use_responses_api" not in captured


def test_abacus_ai_alias_routes_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setattr(
        "tradingagents.llm_clients.openai_client.NormalizedChatOpenAI",
        FakeChatOpenAI,
    )

    client = create_llm_client(provider="abacus_ai", model="openai/gpt-5.4")
    llm = client.get_llm()

    assert isinstance(llm, FakeChatOpenAI)
    assert captured["model"] == "openai/gpt-5.4"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == "openrouter-test-key"
    assert "use_responses_api" not in captured


def test_provider_definition_maps_legacy_alias_to_canonical_openrouter() -> None:
    definition = get_provider_definition("abacus_ai")

    assert definition.key.value == "openrouter"
    assert definition.default_base_url == "https://openrouter.ai/api/v1"


def test_resolve_provider_bundle_rejects_partial_override() -> None:
    with pytest.raises(ValueError, match="complete provider bundle override"):
        resolve_provider_bundle(
            "openrouter",
            override={"base_url": "https://example.com/v1"},
        )


def test_resolve_provider_bundle_swaps_url_and_key_together() -> None:
    bundle = resolve_provider_bundle("abacus_ai")

    assert bundle.provider == "openrouter"
    assert bundle.base_url == "https://openrouter.ai/api/v1"
    assert bundle.api_key_env == "OPENROUTER_API_KEY"


def test_non_openai_provider_retries_json_decode_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI

    attempts = {"count": 0}

    def fake_generate(self, messages, stop=None, run_manager=None, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise JSONDecodeError("Expecting value", "\n", 0)
        return "ok"

    monkeypatch.setattr(ChatOpenAI, "_generate", fake_generate)
    monkeypatch.setattr("tradingagents.llm_clients.openai_client.time.sleep", lambda _: None)

    llm = NormalizedChatOpenAI(
        model="moonshotai/kimi-k2.6",
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        provider_name="openrouter",
        json_retry_attempts=2,
    )

    assert llm._generate([]) == "ok"
    assert attempts["count"] == 2


def test_openai_provider_does_not_retry_json_decode_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI

    attempts = {"count": 0}

    def fake_generate(self, messages, stop=None, run_manager=None, **kwargs):
        attempts["count"] += 1
        raise JSONDecodeError("Expecting value", "\n", 0)

    monkeypatch.setattr(ChatOpenAI, "_generate", fake_generate)
    monkeypatch.setattr("tradingagents.llm_clients.openai_client.time.sleep", lambda _: None)

    llm = NormalizedChatOpenAI(
        model="gpt-5.4",
        api_key="test-key",
        provider_name="openai",
        json_retry_attempts=0,
    )

    with pytest.raises(JSONDecodeError):
        llm._generate([])

    assert attempts["count"] == 1
