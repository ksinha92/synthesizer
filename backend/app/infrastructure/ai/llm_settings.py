"""Runtime LLM settings backed by Redis with .env fallback."""

from __future__ import annotations

import json

import httpx
import structlog
import redis.asyncio as aioredis

from app.config import settings
from app.domain.shared.errors import DomainError

logger = structlog.get_logger()

REDIS_KEY = "datawrangler:llm_settings"
CLAUDE_MODEL = "claude-sonnet-4-20250514"


_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _looks_localhost(url: str) -> bool:
    """Heuristic for a URL that points at the same machine as the caller."""
    if not url:
        return False
    return any(h in url for h in _LOCAL_HOSTS)


def _docker_hint(url: str) -> str:
    """Only suggest the Docker indirection when the URL actually uses localhost."""
    if _looks_localhost(url):
        return (
            " If the backend is running in Docker, use "
            "'http://host.docker.internal:11434' instead of 'localhost'."
        )
    return ""


class OllamaConfigError(DomainError):
    """Raised when admin tries to persist an Ollama config the backend can't use.

    Covers: empty URL, unreachable host, non-2xx /api/tags response, body that
    doesn't look like Ollama's, and selected model not present on the server.
    """

    def __init__(self, message: str, code: str = "ollama_unreachable") -> None:
        super().__init__(message=message, code=code)


# Kept as an alias so the admin endpoint's existing import continues to work.
UnreachableLLMEndpointError = OllamaConfigError


async def _probe_ollama(url: str, model: str | None = None) -> None:
    """Validate that ``url`` is reachable, looks like Ollama, and (if given)
    has ``model`` available.

    Raises :class:`OllamaConfigError` with a code suitable for surfacing in
    the admin UI:

    * ``ollama_url_required`` — empty URL
    * ``ollama_unreachable`` — DNS/connect/timeout failure
    * ``ollama_bad_response`` — non-2xx or body not in Ollama's shape
    * ``ollama_model_not_installed`` — server reachable but model not pulled
    """
    if not url or not url.strip():
        raise OllamaConfigError(
            "Ollama URL is required when the provider is set to 'ollama'.",
            code="ollama_url_required",
        )

    probe = url.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(probe)
    except httpx.HTTPError as e:
        raise OllamaConfigError(
            f"Backend can't reach Ollama at {url!r}: {type(e).__name__}: {e}."
            + _docker_hint(url),
            code="ollama_unreachable",
        )

    if resp.status_code // 100 != 2:
        raise OllamaConfigError(
            f"Ollama at {url!r} returned HTTP {resp.status_code} on /api/tags."
            f" Check the URL is correct and is actually pointing at an Ollama server."
            + _docker_hint(url),
            code="ollama_bad_response",
        )

    try:
        body = resp.json()
    except ValueError:
        raise OllamaConfigError(
            f"Response from {probe!r} wasn't JSON. The URL probably isn't an Ollama server.",
            code="ollama_bad_response",
        )

    if not isinstance(body, dict) or "models" not in body or not isinstance(body["models"], list):
        raise OllamaConfigError(
            f"Response from {probe!r} doesn't match Ollama's shape "
            "(expected an object with a 'models' array). The URL probably isn't an Ollama server.",
            code="ollama_bad_response",
        )

    if model:
        installed = {
            m.get("name", "")
            for m in body["models"]
            if isinstance(m, dict)
        }
        # Ollama returns names like "llama3.2:3b"; accept both the exact match
        # and the bare name (a saved "llama3.2" matches an installed "llama3.2:latest").
        bare_names = {n.split(":", 1)[0] for n in installed if n}
        if model not in installed and model.split(":", 1)[0] not in bare_names:
            sample = sorted(installed)[:6]
            raise OllamaConfigError(
                f"Model {model!r} isn't available on Ollama at {url!r}. "
                f"Installed models include: {', '.join(sample) or '(none)'}. "
                f"Pull it with `ollama pull {model}` or pick one of the installed names.",
                code="ollama_model_not_installed",
            )


async def _get_redis():
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _env_defaults() -> dict:
    """Fall back to .env values."""
    return {
        "provider": settings.LLM_PROVIDER,
        "claude_api_key": settings.CLAUDE_API_KEY,
        "ollama_url": settings.OLLAMA_URL,
        "ollama_model": settings.OLLAMA_MODEL,
        "litellm_url": settings.LITELLM_URL,
        "litellm_api_key": settings.LITELLM_API_KEY,
        "litellm_model": settings.LITELLM_MODEL,
        "litellm_verify_ssl": settings.LITELLM_VERIFY_SSL,
        "litellm_no_proxy": settings.LITELLM_NO_PROXY,
    }


async def get_llm_settings() -> dict:
    """Read LLM settings for API responses. Never exposes raw API keys."""
    raw = await get_llm_settings_raw()
    return {
        "provider": raw["provider"],
        "has_api_key": bool(raw.get("claude_api_key")),
        "ollama_url": raw["ollama_url"],
        "ollama_model": raw["ollama_model"],
        "claude_model": CLAUDE_MODEL,
        "litellm_url": raw.get("litellm_url", ""),
        "has_litellm_api_key": bool(raw.get("litellm_api_key")),
        "litellm_model": raw.get("litellm_model", "gpt-4o-mini"),
        "litellm_verify_ssl": bool(raw.get("litellm_verify_ssl", True)),
        "litellm_no_proxy": raw.get("litellm_no_proxy", "") or "",
    }


async def get_llm_settings_raw() -> dict:
    """Read LLM settings including secrets. For internal use only."""
    try:
        r = await _get_redis()
        data = await r.get(REDIS_KEY)
        await r.aclose()
        if data:
            return {**_env_defaults(), **json.loads(data)}
    except Exception as e:
        await logger.awarning("llm_settings_redis_fallback", error=str(e))
    return _env_defaults()


async def save_llm_settings(data: dict) -> None:
    """Save LLM settings to Redis. Preserves existing API key if not provided."""
    current = await get_llm_settings_raw()

    # Pydantic's model_dump() emits keys with None values for fields the caller
    # omitted, so plain `data.get(k, current[k])` would *overwrite* a stored
    # value with None. Treat None as "no change" for every optional field.
    def _pick(key: str, fallback):
        v = data.get(key)
        return fallback if v is None else v

    updated = {
        "provider": _pick("provider", current["provider"]),
        "ollama_url": _pick("ollama_url", current["ollama_url"]),
        "ollama_model": _pick("ollama_model", current["ollama_model"]),
        "litellm_url": _pick("litellm_url", current.get("litellm_url", "")),
        "litellm_model": _pick("litellm_model", current.get("litellm_model", "gpt-4o-mini")),
        "litellm_verify_ssl": bool(_pick("litellm_verify_ssl", current.get("litellm_verify_ssl", True))),
        "litellm_no_proxy": (_pick("litellm_no_proxy", current.get("litellm_no_proxy", "")) or ""),
    }

    # Only update API key if explicitly provided (non-empty)
    new_key = data.get("claude_api_key")
    if new_key:
        updated["claude_api_key"] = new_key
    else:
        updated["claude_api_key"] = current.get("claude_api_key", "")

    new_litellm_key = data.get("litellm_api_key")
    if new_litellm_key:
        updated["litellm_api_key"] = new_litellm_key
    else:
        updated["litellm_api_key"] = current.get("litellm_api_key", "")

    # Pre-flight validation when persisting an Ollama config — refuse to save
    # a URL the backend can't actually use, a response that doesn't look like
    # Ollama, or a model that isn't pulled. Catches the common "localhost
    # from inside a container" footgun + the silently-broken-after-save
    # cases (wrong port, missing model, reverse-proxy returning 404, etc.)
    # before they break the assistant on the next chat.
    if updated["provider"] == "ollama":
        await _probe_ollama(updated["ollama_url"], updated.get("ollama_model"))

    try:
        r = await _get_redis()
        await r.set(REDIS_KEY, json.dumps(updated))
        await r.aclose()
        await logger.ainfo("llm_settings_saved", provider=updated["provider"])
    except Exception as e:
        await logger.aerror("llm_settings_save_failed", error=str(e))
        raise
