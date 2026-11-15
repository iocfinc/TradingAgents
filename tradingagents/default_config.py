import json
import os

from tradingagents.llm_clients.factory import normalize_provider

DEFAULT_ABACUS_BASE_URL = "https://routellm.abacus.ai/v1"

DEFAULT_OPENAI_AGENT_MODEL_MAP = {
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
}


DEFAULT_OPENROUTER_AGENT_MODEL_MAP = {
    "market": "tencent/hy3-preview",
    "social": "tencent/hy3-preview",
    "news": "tencent/hy3-preview",
    "fundamentals": "tencent/hy3-preview",
    "risk_reflection": "tencent/hy3-preview",
    "bull_researcher": "tencent/hy3-preview",
    "bear_researcher": "tencent/hy3-preview",
    "research_manager": "tencent/hy3-preview",
    "trader": "tencent/hy3-preview",
    "portfolio_manager": "tencent/hy3-preview",
}


def _provider_default_agent_model_map(provider: str) -> dict[str, str]:
    provider_key = normalize_provider(provider)
    if provider_key == "openrouter":
        return DEFAULT_OPENROUTER_AGENT_MODEL_MAP.copy()
    return DEFAULT_OPENAI_AGENT_MODEL_MAP.copy()


def get_default_agent_model_map(provider: str | None = None) -> dict[str, str]:
    provider_key = normalize_provider(
        provider or os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai")
    )
    model_map = _provider_default_agent_model_map(provider_key)
    raw = os.getenv("ABACUS_AGENT_MODEL_MAP", "").strip()
    if not raw:
        return model_map

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return model_map

    if not isinstance(payload, dict):
        return model_map

    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            model_map[key] = value.strip()
    return model_map

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOCAL_STATE_ROOT = os.path.join(_REPO_ROOT, ".local-state")

_DEFAULT_PROVIDER = normalize_provider(
    os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai")
)
_DEFAULT_DEEP_MODEL = os.getenv(
    "ABACUS_DEEP_MODEL",
    "tencent/hy3-preview" if _DEFAULT_PROVIDER == "openrouter" else "gpt-5.4",
)
_DEFAULT_QUICK_MODEL = os.getenv(
    "ABACUS_QUICK_MODEL",
    "tencent/hy3-preview" if _DEFAULT_PROVIDER == "openrouter" else "gpt-5.4-mini",
)

DEFAULT_CONFIG = {
    "project_dir": _REPO_ROOT,
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_LOCAL_STATE_ROOT, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_LOCAL_STATE_ROOT, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_LOCAL_STATE_ROOT, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": _DEFAULT_PROVIDER,
    "deep_think_llm": _DEFAULT_DEEP_MODEL,
    "quick_think_llm": _DEFAULT_QUICK_MODEL,
    "agent_model_map": get_default_agent_model_map(_DEFAULT_PROVIDER),
    # Explicit provider endpoint overrides must be supplied atomically with an
    # api_key_env via provider_bundle_override. Normal runs rely on the
    # canonical provider registry instead of a detached backend_url field.
    "provider_bundle_override": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
