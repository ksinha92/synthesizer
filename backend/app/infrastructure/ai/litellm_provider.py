"""LiteLLM provider — talks to any OpenAI-compatible /v1/chat/completions endpoint.

Covers self-hosted LiteLLM proxies, Azure OpenAI deployments, AWS Bedrock gateways,
and enterprise on-prem LLM routers that expose the OpenAI Chat Completions API.

Supports:
  - Custom base URL (e.g. https://litellm.corp.internal/v1)
  - Bearer SK API key (sk-... style)
  - Configurable model name
  - SSL certificate verification toggle (for internal CAs)
  - NO_PROXY override (hosts/CIDRs to bypass HTTP_PROXY / HTTPS_PROXY for this call)
"""

from __future__ import annotations

import ipaddress
import json
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

from app.domain.shared.errors import AuthenticationError
from app.infrastructure.ai.llm_provider import LLMProvider, ProviderConfig

logger = structlog.get_logger()


@dataclass
class LiteLLMOptions:
    verify_ssl: bool = True
    no_proxy: str = ""


def _host_matches_no_proxy(host: str, no_proxy: str) -> bool:
    """Return True if `host` should bypass proxies per the no_proxy spec.

    Supports the conventions admins expect from `NO_PROXY` env vars:
      - exact host:        `litellm.corp.internal`
      - bare suffix:       `internal` matches `internal` AND `*.internal`
      - leading-dot:       `.internal` matches `*.internal` ONLY — NOT the
                           bare host `internal`. This follows the Go/AWS-CLI
                           interpretation: the dot signals "subdomains only".
      - CIDR ranges:       `10.0.0.0/8`, `fd00::/8`
      - IP literals:       `192.168.1.10`, `::1`, `[::1]`, `0:0:0:0:0:0:0:1`
      - `*` matches everything

    IP-literal entries are compared via the `ipaddress` module so canonical
    and expanded forms of the same address match. Suffix matching only
    applies to hostnames; it is never applied to IP-literal hosts.
    """
    if not no_proxy or not host:
        return False
    # urlparse(...).hostname strips IPv6 brackets, but be defensive in case a
    # bracketed literal flows in from elsewhere.
    host = host.lower().strip("[]").rstrip(".")
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        host_ip = None

    for raw in no_proxy.split(","):
        entry = raw.strip().lower().strip("[]")
        if not entry:
            continue
        if entry == "*":
            return True
        if "/" in entry:
            try:
                net = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                continue
            if host_ip is None:
                continue
            try:
                if host_ip in net:
                    return True
            except TypeError:
                # Mixed IPv4/IPv6 — `in` raises on some Python versions.
                pass
            continue
        # IP-literal entry: canonicalize via ipaddress so `::1` == `[::1]` ==
        # `0:0:0:0:0:0:0:1`. If the host is also an IP, compare as IPs; if it
        # isn't, an IP entry simply cannot match.
        try:
            entry_ip = ipaddress.ip_address(entry)
        except ValueError:
            entry_ip = None
        if entry_ip is not None:
            if host_ip is not None and host_ip == entry_ip:
                return True
            continue
        # Hostname suffix / exact match — never applied to IP-literal hosts.
        if host_ip is not None:
            continue
        if entry.startswith("."):
            # Leading-dot = subdomains only. `.internal` matches `foo.internal`
            # but NOT bare `internal`. `host.endswith(entry)` enforces the dot.
            if host.endswith(entry):
                return True
        else:
            if host == entry or host.endswith("." + entry):
                return True
    return False


class LiteLLMProvider(LLMProvider):
    """OpenAI-compatible client for LiteLLM proxies and equivalent gateways."""

    def __init__(self, config: ProviderConfig, options: LiteLLMOptions | None = None) -> None:
        super().__init__(config)
        self._base_url = config.base_url.rstrip("/")
        self._options = options or LiteLLMOptions()

    def _chat_url(self) -> str:
        # Allow the operator to point at either the proxy root or directly at the
        # /v1 path — both are common in LiteLLM deployments.
        if self._base_url.endswith("/v1") or "/v1/" in self._base_url:
            return f"{self._base_url}/chat/completions"
        return f"{self._base_url}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._config.api_key:
            h["Authorization"] = f"Bearer {self._config.api_key}"
        return h

    def _target_host(self) -> str:
        try:
            return (urlparse(self._base_url).hostname or "").lower()
        except Exception:
            return ""

    def _bypass_proxy(self) -> bool:
        return _host_matches_no_proxy(self._target_host(), self._options.no_proxy)

    def _client(self) -> httpx.AsyncClient:
        # The LiteLLM client only ever talks to `self._base_url`, so we decide
        # proxy routing once per request based on whether the target host
        # matches the configured no_proxy list.
        #
        # IMPORTANT: keep `trust_env=True` even when bypassing the proxy.
        # `trust_env` gates more than HTTP_PROXY / HTTPS_PROXY — it also gates
        # `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` lookup. Internal LiteLLM
        # endpoints are exactly the ones likely to be signed by a corporate
        # CA configured via env, so disabling env reading here would break
        # TLS verification against that CA.
        #
        # To bypass the proxy without losing env-based SSL trust, mount a
        # non-proxy transport for every URL. The transport defaults to
        # `trust_env=True`, so it still picks up env CA bundles, but it does
        # not consult HTTP_PROXY / HTTPS_PROXY.
        #
        # IMPORTANT: a plain `all://` mount is NOT enough. With `trust_env=True`,
        # httpx pre-populates `https://` and `http://` mounts pointing at the
        # env proxies, and httpx's URLPattern priority ranks scheme-specific
        # patterns ABOVE the catch-all `all://`. So we have to override the
        # scheme keys directly. URLPattern equality is by the pattern string,
        # which lets `dict.update` (inside httpx's Client.__init__) replace the
        # env-derived proxy mounts at those exact keys. We also add a
        # host-specific `all://<host>` mount as belt-and-suspenders — that
        # pattern outranks `https://` on priority for the target host.
        if self._bypass_proxy():
            direct = httpx.AsyncHTTPTransport(verify=self._options.verify_ssl)
            mounts: dict[str, httpx.AsyncBaseTransport] = {
                "https://": direct,
                "http://": direct,
            }
            host = self._target_host()
            if host:
                # `urlparse(...).hostname` returns IPv6 literals unbracketed
                # (e.g. "::1"), but httpx URLPattern parses authority strings
                # via httpx.URL — `URL("all://::1")` raises `InvalidURL` because
                # the second colon is read as a port separator. Bracket IPv6.
                try:
                    ip = ipaddress.ip_address(host)
                    is_ipv6 = ip.version == 6
                except ValueError:
                    is_ipv6 = False
                pattern_host = f"[{host}]" if is_ipv6 else host
                mounts[f"all://{pattern_host}"] = direct
            return httpx.AsyncClient(
                timeout=self._config.timeout,
                verify=self._options.verify_ssl,
                mounts=mounts,
                trust_env=True,
            )
        return httpx.AsyncClient(
            timeout=self._config.timeout,
            verify=self._options.verify_ssl,
            trust_env=True,
        )

    async def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self.check_budget():
            raise AuthenticationError(message="LLM call budget exhausted", code="llm_budget_exhausted")
        if not self._base_url:
            raise AuthenticationError(message="LiteLLM URL is not configured", code="litellm_unconfigured")

        start = time.monotonic()
        try:
            async with self._client() as client:
                response = await client.post(
                    self._chat_url(),
                    headers=self._headers(),
                    json={
                        "model": self._config.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()

            self.increment_call_count()
            latency = time.monotonic() - start

            choices = data.get("choices") or []
            text = (choices[0].get("message") or {}).get("content", "") if choices else ""
            usage = data.get("usage") or {}
            await logger.ainfo(
                "litellm_completion",
                model=self._config.model,
                latency_ms=round(latency * 1000),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            return text

        except httpx.ConnectError as e:
            raise AuthenticationError(
                message=f"LiteLLM not reachable at {self._base_url}: {e}",
                code="litellm_unreachable",
            ) from e
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                message=f"LiteLLM API error: {e.response.status_code} {e.response.text[:200]}",
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
        text = await self.complete(structured_prompt, max_tokens=2048)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return {}
