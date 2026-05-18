"""Regression tests for the LiteLLM no-proxy bypass + matcher.

These pin down behavior that was iterated on through several Codex review
passes. Each `xfail`-able case in here corresponds to a bug that shipped
during that iteration:

  - dict.get() returning Pydantic-emitted None corrupting saved LiteLLM
    settings on partial PUT.
  - `trust_env=False` bypass also disabling SSL_CERT_FILE lookup,
    breaking internal-CA TLS.
  - `all://` mount losing URLPattern-priority to env's `https://` mount,
    so HTTPS_PROXY was never actually bypassed.
  - IPv6 hostnames crashing the URLPattern parser with `InvalidURL`.
  - Leading-dot `.internal` matching the bare host `internal`, broadening
    proxy bypass beyond Go/AWS-CLI semantics.

The tests do NOT hit the network. They inspect the resolved transport's
pool type (`AsyncConnectionPool` vs `AsyncHTTPProxy`) and the matcher's
return value, so they are deterministic and fast.
"""

from __future__ import annotations

import httpx
import pytest

from app.infrastructure.ai.litellm_provider import (
    LiteLLMOptions,
    LiteLLMProvider,
    _host_matches_no_proxy,
)
from app.infrastructure.ai.llm_provider import ProviderConfig


# ---------------------------------------------------------------------------
# _host_matches_no_proxy: parametrized behavior matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("host", "no_proxy", "expected"),
    [
        # Leading-dot semantics: subdomains only, NOT the bare host.
        ("internal",            ".internal",   False),
        ("foo.internal",        ".internal",   True),
        ("a.b.internal",        ".internal",   True),
        ("myinternal",          ".internal",   False),
        ("externalinternal",    ".internal",   False),

        # No-leading-dot: bare host AND subdomains.
        ("internal",            "internal",    True),
        ("foo.internal",        "internal",    True),
        ("myinternal",          "internal",    False),

        # Exact host match.
        ("litellm.corp.internal", "litellm.corp.internal", True),

        # Wildcard.
        ("anything.com",        "*",           True),

        # Non-matching suffix.
        ("api.external.com",    ".internal",   False),

        # CIDR — IPv4.
        ("10.5.1.4",            "10.0.0.0/8",  True),
        ("172.16.5.4",          "10.0.0.0/8",  False),

        # CIDR — IPv6.
        ("fd12:3456::abc",      "fd00::/8",    True),
        ("::1",                 "fd00::/8",    False),

        # IPv6 canonical-form matching (`::1` == `0:0:0:0:0:0:0:1` == `[::1]`).
        ("::1",                 "::1",                 True),
        ("::1",                 "0:0:0:0:0:0:0:1",     True),
        ("::1",                 "[::1]",               True),

        # IP literals don't get suffix matching applied.
        ("10.0.0.5",            ".internal",   False),
        ("10.0.0.5",            "internal",    False),
        ("::1",                 ".internal",   False),

        # Hostname entries don't match IP-literal hosts.
        ("api.corp.internal",   "::1",         False),

        # Mixed IPv4/IPv6 CIDR doesn't crash.
        ("::1",                 "10.0.0.0/8",  False),
        ("10.0.0.5",            "::1",         False),

        # Multi-entry list, only one valid.
        ("a.b.com",             "bogus/cidr, b.com", True),

        # Empty inputs.
        ("a.b.com",             "",            False),
        ("",                    "anything",    False),

        # Bare IPv4 exact match.
        ("192.168.1.10",        "192.168.1.10", True),
    ],
)
def test_host_matches_no_proxy(host: str, no_proxy: str, expected: bool) -> None:
    assert _host_matches_no_proxy(host, no_proxy) is expected


# ---------------------------------------------------------------------------
# Client transport selection: bypass actually skips HTTPS_PROXY without
# breaking env-driven SSL trust.
# ---------------------------------------------------------------------------


def _build(base_url: str, no_proxy: str, verify_ssl: bool = True) -> LiteLLMProvider:
    return LiteLLMProvider(
        ProviderConfig(provider_name="litellm", base_url=base_url, model="x"),
        LiteLLMOptions(verify_ssl=verify_ssl, no_proxy=no_proxy),
    )


def _pool_for(provider: LiteLLMProvider, url: str) -> str:
    """Return the class name of the connection pool resolved for `url`."""
    client = provider._client()
    try:
        transport = client._transport_for_url(httpx.URL(url))
        return type(transport._pool).__name__
    finally:
        # Sync close is enough — no requests issued.
        client._mounts.clear()


@pytest.fixture
def env_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend a corporate proxy is configured via env."""
    monkeypatch.setenv("HTTPS_PROXY", "http://corp-proxy.internal:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://corp-proxy.internal:3128")
    # NO_PROXY in env must not leak into our matcher's decision.
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)


def test_bypass_skips_https_proxy_for_matching_host(env_proxies: None) -> None:
    provider = _build("https://api.corp.internal/v1", no_proxy=".internal")
    assert provider._bypass_proxy() is True
    # HTTPS to the corp host bypasses the proxy.
    assert _pool_for(provider, "https://api.corp.internal/v1/chat/completions") == "AsyncConnectionPool"
    # HTTP to the corp host bypasses the proxy.
    assert _pool_for(provider, "http://api.corp.internal/v1/chat/completions") == "AsyncConnectionPool"


def test_non_matching_no_proxy_still_uses_env_proxy(env_proxies: None) -> None:
    provider = _build("https://api.corp.internal/v1", no_proxy="other.host")
    assert provider._bypass_proxy() is False
    assert _pool_for(provider, "https://api.corp.internal/v1/chat/completions") == "AsyncHTTPProxy"


def test_empty_no_proxy_uses_env_proxy(env_proxies: None) -> None:
    provider = _build("https://api.corp.internal/v1", no_proxy="")
    assert provider._bypass_proxy() is False
    assert _pool_for(provider, "https://api.corp.internal/v1/chat/completions") == "AsyncHTTPProxy"


def test_leading_dot_does_not_bypass_bare_host(env_proxies: None) -> None:
    """`.internal` must NOT bypass for a bare host `internal`; `internal` does."""
    provider = _build("https://internal/v1", no_proxy=".internal")
    assert provider._bypass_proxy() is False
    assert _pool_for(provider, "https://internal/v1/chat/completions") == "AsyncHTTPProxy"

    provider2 = _build("https://internal/v1", no_proxy="internal")
    assert provider2._bypass_proxy() is True
    assert _pool_for(provider2, "https://internal/v1/chat/completions") == "AsyncConnectionPool"


def test_ipv6_target_does_not_crash_and_bypasses_correctly(env_proxies: None) -> None:
    """Regression: `urlparse` returns IPv6 host unbracketed; the mount key
    must bracket it or httpx.URL raises InvalidURL."""
    provider = _build("https://[::1]:8443/v1", no_proxy="::1")
    assert provider._bypass_proxy() is True
    # If the bracketing fix regressed, _client() would raise InvalidURL.
    assert _pool_for(provider, "https://[::1]:8443/v1/chat/completions") == "AsyncConnectionPool"


def test_ipv4_cidr_bypass(env_proxies: None) -> None:
    provider = _build("https://10.0.0.5/v1", no_proxy="10.0.0.0/8")
    assert provider._bypass_proxy() is True
    assert _pool_for(provider, "https://10.0.0.5/v1/chat/completions") == "AsyncConnectionPool"


def test_bypass_preserves_ssl_cert_file(env_proxies: None, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: an earlier fix used `trust_env=False` which also disabled
    SSL_CERT_FILE lookup, breaking corp-CA TLS to the very endpoint the
    bypass is supposed to reach. The mounted transport must still honour
    env-based CA bundles."""
    import subprocess

    ca = tmp_path / "ca.pem"
    key = tmp_path / "ca.key"
    result = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-subj", "/CN=Test CA", "-days", "1",
            "-keyout", str(key), "-out", str(ca),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip(f"openssl unavailable for SSL_CERT_FILE check: {result.stderr!r}")

    monkeypatch.setenv("SSL_CERT_FILE", str(ca))

    provider = _build("https://api.corp.internal/v1", no_proxy=".internal")
    client = provider._client()
    transport = client._transport_for_url(
        httpx.URL("https://api.corp.internal/v1/chat/completions")
    )
    cert_count = transport._pool._ssl_context.cert_store_stats()["x509"]
    assert cert_count == 1, (
        f"Expected exactly 1 CA cert from SSL_CERT_FILE; got {cert_count}. "
        "trust_env regression — env-configured corp CAs no longer load."
    )


# ---------------------------------------------------------------------------
# save_llm_settings: partial PUTs must not corrupt configured LiteLLM fields.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_put_does_not_corrupt_litellm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `PUT /api/v1/admin/settings/llm` body that switches provider to
    `claude` but leaves litellm_* unset (Pydantic populates them as None)
    must NOT overwrite the stored LiteLLM URL / model / verify_ssl /
    no_proxy / api_key."""
    from app.infrastructure.ai import llm_settings as s

    # In-memory fake Redis — the real one isn't a hard requirement for this
    # test and may not be reachable in every CI runner.
    store: dict[str, str] = {}

    class FakeRedis:
        async def get(self, key: str) -> str | None:
            return store.get(key)

        async def set(self, key: str, value: str) -> None:
            store[key] = value

        async def aclose(self) -> None:
            pass

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(s, "_get_redis", fake_get_redis)

    # 1. Save a full LiteLLM config.
    await s.save_llm_settings(
        {
            "provider": "litellm",
            "litellm_url": "https://litellm.corp.internal/v1",
            "litellm_api_key": "sk-original-secret",
            "litellm_model": "gpt-4o-mini",
            "litellm_verify_ssl": False,
            "litellm_no_proxy": ".internal,10.0.0.0/8",
        }
    )
    before = await s.get_llm_settings_raw()

    # 2. Simulate a 'normal' partial PUT: provider switch, all litellm_* = None.
    await s.save_llm_settings(
        {
            "provider": "claude",
            "claude_api_key": None,
            "ollama_url": "http://localhost:11434",
            "ollama_model": "llama3.1",
            "litellm_url": None,
            "litellm_api_key": None,
            "litellm_model": None,
            "litellm_verify_ssl": None,
            "litellm_no_proxy": None,
        }
    )
    after = await s.get_llm_settings_raw()

    # Provider switched, but every LiteLLM field is preserved.
    assert after["provider"] == "claude"
    for key in (
        "litellm_url",
        "litellm_api_key",
        "litellm_model",
        "litellm_verify_ssl",
        "litellm_no_proxy",
    ):
        assert after[key] == before[key], f"{key} was corrupted: {before[key]!r} -> {after[key]!r}"
