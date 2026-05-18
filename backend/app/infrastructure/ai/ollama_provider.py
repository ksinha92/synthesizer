"""Ollama self-hosted LLM provider."""

from __future__ import annotations

import json
import time

import httpx
import structlog

from app.domain.shared.errors import AuthenticationError
from app.infrastructure.ai.llm_provider import LLMProvider, ProviderConfig

logger = structlog.get_logger()


class OllamaProvider(LLMProvider):
    """Self-hosted LLM via Ollama REST API."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._base_url = config.base_url.rstrip("/")

    async def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self.check_budget():
            raise AuthenticationError(message="LLM call budget exhausted", code="llm_budget_exhausted")

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._config.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                response.raise_for_status()
                data = response.json()

            self.increment_call_count()
            latency = time.monotonic() - start

            text = data.get("response", "")
            await logger.ainfo(
                "ollama_completion",
                model=self._config.model,
                latency_ms=round(latency * 1000),
                eval_count=data.get("eval_count", 0),
            )
            return text

        except httpx.ConnectError:
            raise AuthenticationError(
                message=f"Ollama not reachable at {self._base_url}",
                code="ollama_unreachable",
            )
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                message=f"Ollama API error: {e.response.status_code}",
                code="llm_api_error",
            ) from e

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
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._config.model,
                        "prompt": structured_prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()
            self.increment_call_count()
            return json.loads(data.get("response", "{}"))
        except (json.JSONDecodeError, httpx.HTTPError):
            return {}
