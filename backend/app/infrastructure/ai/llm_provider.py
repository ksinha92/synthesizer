"""LLM provider abstraction — pluggable backend for Claude API and Ollama."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class ProviderConfig:
    provider_name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout: float = 30.0
    max_calls_per_batch: int = 50


class LLMProvider(ABC):
    """Abstract LLM provider. Infrastructure implementations for Claude and Ollama."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._call_count = 0
        self._budget_exhausted = False

    @abstractmethod
    async def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        """Text completion."""
        ...

    @abstractmethod
    async def classify(self, prompt: str, options: list[str]) -> tuple[str, float]:
        """Classification with confidence score."""
        ...

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        """Structured JSON output."""
        ...

    def check_budget(self) -> bool:
        """Check if call budget is exhausted."""
        if self._call_count >= self._config.max_calls_per_batch:
            if not self._budget_exhausted:
                self._budget_exhausted = True
                logger.warning("llm_budget_exhausted", calls=self._call_count, limit=self._config.max_calls_per_batch)
            return False
        return True

    def increment_call_count(self) -> None:
        self._call_count += 1

    def reset_budget(self) -> None:
        self._call_count = 0
        self._budget_exhausted = False


def create_provider(settings) -> LLMProvider | None:
    """Factory: create LLM provider from application settings."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "claude":
        if not settings.CLAUDE_API_KEY:
            logger.warning("llm_provider_skipped", reason="CLAUDE_API_KEY not set")
            return None
        from app.infrastructure.ai.claude_provider import ClaudeProvider
        config = ProviderConfig(
            provider_name="claude",
            api_key=settings.CLAUDE_API_KEY,
            model="claude-sonnet-4-20250514",
            timeout=30.0,
        )
        return ClaudeProvider(config)

    elif provider == "ollama":
        from app.infrastructure.ai.ollama_provider import OllamaProvider
        config = ProviderConfig(
            provider_name="ollama",
            base_url=settings.OLLAMA_URL,
            model="llama3.1",
            timeout=60.0,
        )
        return OllamaProvider(config)

    elif provider == "litellm":
        if not settings.LITELLM_URL:
            logger.warning("llm_provider_skipped", reason="LITELLM_URL not set")
            return None
        from app.infrastructure.ai.litellm_provider import LiteLLMProvider, LiteLLMOptions
        config = ProviderConfig(
            provider_name="litellm",
            api_key=settings.LITELLM_API_KEY,
            base_url=settings.LITELLM_URL,
            model=settings.LITELLM_MODEL,
            timeout=60.0,
        )
        return LiteLLMProvider(
            config,
            LiteLLMOptions(
                verify_ssl=settings.LITELLM_VERIFY_SSL,
                no_proxy=settings.LITELLM_NO_PROXY,
            ),
        )

    else:
        logger.warning("llm_provider_unknown", provider=provider)
        return None


async def create_provider_from_runtime() -> LLMProvider | None:
    """Create LLM provider using runtime settings (Redis) with .env fallback."""
    from app.infrastructure.ai.llm_settings import get_llm_settings_raw

    raw = await get_llm_settings_raw()
    provider = raw.get("provider", "claude").lower()

    if provider == "claude":
        api_key = raw.get("claude_api_key", "")
        if not api_key:
            logger.warning("llm_provider_skipped", reason="CLAUDE_API_KEY not set")
            return None
        from app.infrastructure.ai.claude_provider import ClaudeProvider
        config = ProviderConfig(
            provider_name="claude",
            api_key=api_key,
            model="claude-sonnet-4-20250514",
            timeout=30.0,
        )
        return ClaudeProvider(config)

    elif provider == "ollama":
        from app.infrastructure.ai.ollama_provider import OllamaProvider
        config = ProviderConfig(
            provider_name="ollama",
            base_url=raw.get("ollama_url", "http://localhost:11434"),
            model=raw.get("ollama_model", "llama3.1"),
            timeout=60.0,
        )
        return OllamaProvider(config)

    elif provider == "litellm":
        base_url = raw.get("litellm_url", "")
        if not base_url:
            logger.warning("llm_provider_skipped", reason="litellm_url not set")
            return None
        from app.infrastructure.ai.litellm_provider import LiteLLMProvider, LiteLLMOptions
        config = ProviderConfig(
            provider_name="litellm",
            api_key=raw.get("litellm_api_key", ""),
            base_url=base_url,
            model=raw.get("litellm_model", "gpt-4o-mini"),
            timeout=60.0,
        )
        return LiteLLMProvider(
            config,
            LiteLLMOptions(
                verify_ssl=bool(raw.get("litellm_verify_ssl", True)),
                no_proxy=raw.get("litellm_no_proxy", "") or "",
            ),
        )

    else:
        logger.warning("llm_provider_unknown", provider=provider)
        return None
