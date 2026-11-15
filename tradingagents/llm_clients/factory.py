import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .base_client import BaseLLMClient


class Provider(str, Enum):
    OPENAI = "openai"
    ABACUS = "abacus"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    GLM = "glm"
    OPENROUTER = "openrouter"
    AZURE = "azure"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderDefinition:
    key: Provider
    display_name: str
    default_base_url: str | None
    api_key_env: str | None
    openai_compatible: bool = False
    aliases: tuple[str, ...] = ()


PROVIDER_DEFINITIONS = (
    ProviderDefinition(Provider.OPENAI, "OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY", True),
    ProviderDefinition(Provider.ABACUS, "Abacus", "https://routellm.abacus.ai/v1", "ABACUS_API_KEY", True),
    ProviderDefinition(Provider.GOOGLE, "Google", None, "GOOGLE_API_KEY"),
    ProviderDefinition(Provider.ANTHROPIC, "Anthropic", "https://api.anthropic.com/", "ANTHROPIC_API_KEY"),
    ProviderDefinition(Provider.XAI, "xAI", "https://api.x.ai/v1", "XAI_API_KEY", True),
    ProviderDefinition(Provider.DEEPSEEK, "DeepSeek", "https://api.deepseek.com", "DEEPSEEK_API_KEY", True),
    ProviderDefinition(
        Provider.QWEN,
        "Qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_API_KEY",
        True,
    ),
    ProviderDefinition(Provider.GLM, "GLM", "https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY", True),
    ProviderDefinition(
        Provider.OPENROUTER,
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        True,
        aliases=("abacus_ai",),
    ),
    ProviderDefinition(Provider.AZURE, "Azure OpenAI", None, "AZURE_OPENAI_API_KEY"),
    ProviderDefinition(Provider.OLLAMA, "Ollama", "http://localhost:11434/v1", None, True),
)

PROVIDER_ALIASES = {
    alias: definition.key.value
    for definition in PROVIDER_DEFINITIONS
    for alias in definition.aliases
}


@dataclass(frozen=True)
class ProviderBundle:
    provider: str
    base_url: str | None
    api_key_env: str | None

    def asdict(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
        }


def normalize_provider(provider: str) -> str:
    """Map a provider flag/param to its canonical enum value."""
    provider_lower = provider.lower()
    return PROVIDER_ALIASES.get(provider_lower, provider_lower)


def get_provider_definition(provider: str) -> ProviderDefinition:
    canonical = normalize_provider(provider)
    for definition in PROVIDER_DEFINITIONS:
        if definition.key.value == canonical:
            return definition
    raise ValueError(f"Unsupported LLM provider: {provider}")


def resolve_provider_bundle(
    provider: str,
    override: Optional[dict[str, str | None]] = None,
) -> ProviderBundle:
    definition = get_provider_definition(provider)

    if override is None:
        return ProviderBundle(
            provider=definition.key.value,
            base_url=definition.default_base_url,
            api_key_env=definition.api_key_env,
        )

    base_url = override.get("base_url")
    api_key_env = override.get("api_key_env")
    if not base_url or not api_key_env:
        raise ValueError(
            "A complete provider bundle override with both base_url and api_key_env is required."
        )

    return ProviderBundle(
        provider=definition.key.value,
        base_url=base_url,
        api_key_env=api_key_env,
    )


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    provider_bundle_override: Optional[dict[str, str | None]] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Provider modules are imported lazily so that simply importing this
    factory (e.g. during test collection) does not pull in heavy LLM SDKs
    or fail when their API keys are absent.

    Args:
        provider: LLM provider name
        model: Model name/identifier
        base_url: Optional base URL for API endpoint
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured BaseLLMClient instance

    Raises:
        ValueError: If provider is not supported
    """
    if base_url is not None:
        raise ValueError(
            "Standalone base_url overrides are not supported. "
            "Use provider_bundle_override with both base_url and api_key_env."
        )

    definition = get_provider_definition(provider)
    bundle = resolve_provider_bundle(provider, override=provider_bundle_override)
    provider_lower = definition.key.value

    if definition.openai_compatible:
        from .openai_client import OpenAIClient
        if bundle.api_key_env:
            api_key = os.environ.get(bundle.api_key_env)
            if api_key:
                kwargs.setdefault("api_key", api_key)
        return OpenAIClient(model, bundle.base_url, provider=provider_lower, **kwargs)

    if provider_lower == Provider.ANTHROPIC.value:
        from .anthropic_client import AnthropicClient
        return AnthropicClient(model, bundle.base_url, **kwargs)

    if provider_lower == Provider.GOOGLE.value:
        from .google_client import GoogleClient
        return GoogleClient(model, bundle.base_url, **kwargs)

    if provider_lower == Provider.AZURE.value:
        from .azure_client import AzureOpenAIClient
        return AzureOpenAIClient(model, bundle.base_url, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
