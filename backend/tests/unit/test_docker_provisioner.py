"""Unit tests for ``DockerProvisioner`` (Phase 61 F18).

We never touch a real Docker daemon -- ``asyncio.create_subprocess_exec``
is patched to return a fabricated process object that mimics ``docker
run`` / ``docker exec`` / ``docker stop`` / ``docker rm`` outcomes.
Coverage targets:

* ``provision`` picks a host port in [40000, 50000) and builds the
  correct argv per engine.
* ``provision`` retries on docker-run failure and surfaces a
  ``ProvisionError`` after the retry budget is exhausted.
* ``wait_for_ready`` returns True on the first successful health probe
  and False on timeout.
* ``stop_and_remove`` issues both ``stop`` and ``rm``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.ephemeral.docker_provisioner import (
    HOST_PORT_MAX,
    HOST_PORT_MIN,
    ContainerHandle,
    DockerProvisioner,
    ProvisionError,
)


def _fake_proc(returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    """Build a fake ``asyncio.subprocess.Process`` for one subprocess call.

    Only ``communicate`` and ``returncode`` are exercised by the
    provisioner, so we don't bother modelling the rest. ``communicate``
    is awaited so it must be an ``AsyncMock``.
    """
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def test_provision_returns_handle_with_host_port_in_range():
    """Happy path: a single ``docker run`` succeeds and the handle has
    a host_port inside [HOST_PORT_MIN, HOST_PORT_MAX]."""
    captured_args: list[list[str]] = []

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        captured_args.append(list(args))
        return _fake_proc(0, stdout=b"abc123container\n")

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ):
        handle = asyncio.run(
            DockerProvisioner().provision(
                env_id="env-1234567890abcdef",
                engine="postgresql",
                db_name="mydb",
                root_user="dataw",
                root_password="pw",
            )
        )

    assert isinstance(handle, ContainerHandle)
    assert handle.container_id == "abc123container"
    assert HOST_PORT_MIN <= handle.host_port <= HOST_PORT_MAX
    # Verify the argv carried the right image + port mapping.
    argv = captured_args[0]
    assert argv[0:3] == ["docker", "run", "-d"]
    assert "postgres:15-alpine" in argv
    # -p HOST:CONTAINER for postgres should be HOST:5432
    port_arg = argv[argv.index("-p") + 1]
    assert port_arg.endswith(":5432")


def test_provision_retries_then_fails_with_provision_error():
    """All retries fail -> ``ProvisionError`` with the last stderr."""
    call_count = {"n": 0}

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        call_count["n"] += 1
        return _fake_proc(1, stderr=b"port already in use")

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ):
        with pytest.raises(ProvisionError) as exc_info:
            asyncio.run(
                DockerProvisioner().provision(
                    env_id="env-failure",
                    engine="mysql",
                    db_name="mydb",
                    root_user="u",
                    root_password="p",
                )
            )

    assert "port already in use" in str(exc_info.value)
    # PROVISION_MAX_RETRIES is 5
    assert call_count["n"] == 5


def test_provision_rejects_unsupported_engine():
    """Unknown engine raises before any subprocess is spawned."""
    with pytest.raises(ProvisionError):
        asyncio.run(
            DockerProvisioner().provision(
                env_id="x",
                engine="oracle",  # unsupported
                db_name="db",
                root_user="u",
                root_password="p",
            )
        )


def test_wait_for_ready_times_out_cleanly():
    """If health check never succeeds we return False, not loop forever."""

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        # Always returns non-zero -> never ready.
        return _fake_proc(1)

    # Short-circuit asyncio.sleep so the loop iterates many times in
    # a millisecond. Timeout=1 means at most ~one second wall-clock.
    async def _no_sleep(_):
        return None

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ), patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.sleep",
        new=_no_sleep,
    ):
        ready = asyncio.run(
            DockerProvisioner().wait_for_ready(
                container_id="abc",
                engine="postgresql",
                host_port=40000,
                timeout=1,
            )
        )

    assert ready is False


def test_wait_for_ready_returns_true_on_first_success():
    """First health probe succeeds -> return True immediately."""

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        return _fake_proc(0, stdout=b"ok")

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ):
        ready = asyncio.run(
            DockerProvisioner().wait_for_ready(
                container_id="abc",
                engine="postgresql",
                host_port=40000,
                timeout=10,
            )
        )

    assert ready is True


def test_stop_and_remove_issues_both_commands():
    """stop_and_remove must shell ``docker stop`` *and* ``docker rm``."""
    verbs_seen: list[str] = []

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        # args is ("docker", verb, container_id, ...) for stop/rm.
        verbs_seen.append(args[1])
        return _fake_proc(0)

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ):
        asyncio.run(DockerProvisioner().stop_and_remove("container-xyz"))

    assert verbs_seen == ["stop", "rm"]


def test_stop_and_remove_tolerates_failed_stop():
    """Failure on ``docker stop`` must not prevent ``docker rm`` from running."""
    verbs_seen: list[str] = []

    async def _spawn(*args, **kwargs):  # noqa: ARG001
        verbs_seen.append(args[1])
        # stop fails (container already dead, e.g.); rm should still run.
        rc = 1 if args[1] == "stop" else 0
        return _fake_proc(rc, stderr=b"already stopped")

    with patch(
        "app.infrastructure.ephemeral.docker_provisioner.asyncio.create_subprocess_exec",
        new=_spawn,
    ):
        asyncio.run(DockerProvisioner().stop_and_remove("container-xyz"))

    assert verbs_seen == ["stop", "rm"]
