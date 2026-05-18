"""Claude API provider via Anthropic SDK."""

from __future__ import annotations

import json
import time

import structlog
from anthropic import AsyncAnthropic, APIError

from app.domain.shared.errors import AuthenticationError
from app.infrastructure.ai.llm_provider import LLMProvider, ProviderConfig

logger = structlog.get_logger()


class ClaudeProvider(LLMProvider):
    """Claude API via Anthropic SDK."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = AsyncAnthropic(api_key=config.api_key, timeout=config.timeout)
        self._validated = False
        self._degraded = False

    async def _ensure_validated(self) -> None:
        """Validate API key on first use (lazy init)."""
        if self._validated:
            return
        try:
            # Lightweight validation — minimal completion
            await self._client.messages.create(
                model=self._config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            self._validated = True
            await logger.ainfo("claude_provider_validated", model=self._config.model)
        except APIError as e:
            self._degraded = True
            self._validated = True  # Don't retry validation
            await logger.awarning("claude_provider_degraded", error=str(e), status=getattr(e, "status_code", None))

    async def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        await self._ensure_validated()
        if self._degraded:
            raise AuthenticationError(message="Claude provider is degraded — API key may be invalid", code="llm_degraded")

        if not self.check_budget():
            raise AuthenticationError(message="LLM call budget exhausted", code="llm_budget_exhausted")

        start = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=self._config.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            self.increment_call_count()
            latency = time.monotonic() - start

            text = response.content[0].text if response.content else ""

            await logger.ainfo(
                "claude_completion",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=round(latency * 1000),
                model=self._config.model,
            )
            return text

        except APIError as e:
            await logger.aerror("claude_api_error", error=str(e), status=getattr(e, "status_code", None))
            raise AuthenticationError(message=f"Claude API error: {e}", code="llm_api_error") from e

    async def classify(self, prompt: str, options: list[str]) -> tuple[str, float]:
        classification_prompt = (
            f"{prompt}\n\n"
            f"Respond with ONLY a JSON object: {{\"choice\": \"<one of {options}>\", \"confidence\": <0.0-1.0>}}"
        )
        text = await self.complete(classification_prompt, max_tokens=100)
        try:
            parsed = json.loads(text.strip())
            choice = parsed.get("choice", options[0] if options else "")
            confidence = float(parsed.get("confidence", 0.5))
            return choice, min(max(confidence, 0.0), 1.0)
        except (json.JSONDecodeError, ValueError):
            return options[0] if options else "", 0.3

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        structured_prompt = f"{prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        text = await self.complete(structured_prompt, max_tokens=2048)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {}
