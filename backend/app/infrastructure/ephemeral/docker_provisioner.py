"""Docker-Compose-spawned ephemeral DB provisioner (Phase 61 F18).

This module spins a sidecar container running the requested DB engine
(postgres/mysql/mongodb), binds a random host-port, and waits for the
container to become health-check-ready before handing control back to
the caller.

We deliberately shell out via :func:`asyncio.create_subprocess_exec`
rather than pull in the ``docker`` Python SDK -- the SDK is heavy, it
ships its own Requests + websocket stack, and we only need three CLI
verbs (``run``, ``stop``, ``rm``). ``create_subprocess_exec`` does NOT
invoke a shell; arguments are passed as a list to ``execvp`` directly,
so shell-injection vectors don't apply here.

The provisioner is intentionally infrastructure-only -- the calling
Celery task (``ephemeral_tasks._provision_async``) owns the env-row
state transitions. Keeping the provisioner pure makes the wait/health
loop trivially unit-testable against a mocked subprocess.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


# Image references -- pinned to known-good tags. Bumping these is a
# deliberate operational change because container start-up time and
# health-check shapes vary across major versions.
ENGINE_IMAGES: dict[str, str] = {
    "postgresql": "postgres:15-alpine",
    "mysql": "mysql:8.0",
    "mongodb": "mongo:6",
}

# In-container DB ports we map the random host port to.
ENGINE_CONTAINER_PORTS: dict[str, int] = {
    "postgresql": 5432,
    "mysql": 3306,
    "mongodb": 27017,
}

# Host-port allocation window. Picked above the well-known IANA range and
# below the standard ephemeral-port floor on most Linux installs (which
# starts at 32768) so we don't collide with kernel-allocated sockets.
HOST_PORT_MIN = 40000
HOST_PORT_MAX = 50000
PROVISION_MAX_RETRIES = 5


@dataclass
class ContainerHandle:
    """Reference to a successfully-provisioned ephemeral container.

    Returned by :meth:`DockerProvisioner.provision`. The caller stores
    ``container_id`` + ``host_port`` on the ephemeral_environments row so
    the sweep task can stop the container and so the connection_string
    column points at the right port.
    """

    container_id: str
    host_port: int
    root_user: str
    root_password: str
    engine: str


class ProvisionError(RuntimeError):
    """Raised when ``docker run`` ultimately fails after retries."""


class DockerProvisioner:
    """Async wrapper around the ``docker`` CLI.

    Stateless -- every method is a fresh subprocess invocation. Safe to
    instantiate once at module scope or per-call; we lean on the latter
    inside the Celery task to keep the dependency graph explicit.
    """

    async def provision(
        self,
        env_id: str,
        engine: str,
        db_name: str,
        root_user: str,
        root_password: str,
    ) -> ContainerHandle:
        """Spin a container; return its handle once ``docker run`` reports success.

        Retries up to :data:`PROVISION_MAX_RETRIES` times on failure to
        absorb host-port collisions (random selection can pick a port
        another process just grabbed). Each retry picks a fresh port.
        ``wait_for_ready`` is the caller's job -- ``docker run -d`` only
        guarantees the container was scheduled, not that the DB is
        accepting connections yet.
        """
        if engine not in ENGINE_IMAGES:
            raise ProvisionError(f"unsupported engine: {engine}")

        image = ENGINE_IMAGES[engine]
        container_port = ENGINE_CONTAINER_PORTS[engine]
        container_name = f"datawrangler-eph-{env_id[:12]}"
        last_error: str | None = None

        for attempt in range(PROVISION_MAX_RETRIES):
            host_port = random.randint(HOST_PORT_MIN, HOST_PORT_MAX)
            args = self._docker_run_args(
                container_name=f"{container_name}-{attempt}" if attempt > 0 else container_name,
                image=image,
                engine=engine,
                host_port=host_port,
                container_port=container_port,
                db_name=db_name,
                root_user=root_user,
                root_password=root_password,
            )
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                container_id = stdout.decode().strip().split("\n")[0]
                if not container_id:
                    last_error = "docker run returned empty container id"
                    continue
                await logger.ainfo(
                    "ephemeral_container_started",
                    env_id=env_id,
                    container_id=container_id,
                    host_port=host_port,
                    engine=engine,
                )
                return ContainerHandle(
                    container_id=container_id,
                    host_port=host_port,
                    root_user=root_user,
                    root_password=root_password,
                    engine=engine,
                )

            last_error = stderr.decode().strip() or "docker run failed"
            await logger.awarning(
                "ephemeral_container_retry",
                env_id=env_id,
                attempt=attempt + 1,
                host_port=host_port,
                error=last_error,
            )

        raise ProvisionError(
            f"failed to provision after {PROVISION_MAX_RETRIES} attempts: {last_error}"
        )

    @staticmethod
    def _docker_run_args(
        container_name: str,
        image: str,
        engine: str,
        host_port: int,
        container_port: int,
        db_name: str,
        root_user: str,
        root_password: str,
    ) -> list[str]:
        """Build the ``docker run`` argv list per engine.

        Each engine has its own env-var contract for bootstrapping the
        root user / initial DB. Centralised here so the per-engine
        invariants stay visible.
        """
        base = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "-p",
            f"{host_port}:{container_port}",
        ]
        if engine == "postgresql":
            base += [
                "-e",
                f"POSTGRES_USER={root_user}",
                "-e",
                f"POSTGRES_PASSWORD={root_password}",
                "-e",
                f"POSTGRES_DB={db_name}",
                image,
            ]
        elif engine == "mysql":
            base += [
                "-e",
                f"MYSQL_ROOT_PASSWORD={root_password}",
                "-e",
                f"MYSQL_DATABASE={db_name}",
                "-e",
                f"MYSQL_USER={root_user}",
                "-e",
                f"MYSQL_PASSWORD={root_password}",
                image,
            ]
        else:  # mongodb
            base += [
                "-e",
                f"MONGO_INITDB_ROOT_USERNAME={root_user}",
                "-e",
                f"MONGO_INITDB_ROOT_PASSWORD={root_password}",
                "-e",
                f"MONGO_INITDB_DATABASE={db_name}",
                image,
            ]
        return base

    async def wait_for_ready(
        self,
        container_id: str,
        engine: str,
        host_port: int,
        timeout: int = 60,
    ) -> bool:
        """Poll the container until its DB accepts a trivial query.

        Postgres / MySQL / Mongo each have their own in-image health
        binary (``pg_isready``, ``mysqladmin ping``, ``mongosh --eval``);
        we shell each one through ``docker exec`` once per second until
        either it succeeds or ``timeout`` elapses. Returns False on
        timeout so the caller can flip the env to ``failed`` rather than
        spin forever.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        check = _HEALTH_CHECKS.get(engine)
        if check is None:
            raise ProvisionError(f"no health check for engine: {engine}")

        while asyncio.get_event_loop().time() < deadline:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                container_id,
                *check,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                return True
            await asyncio.sleep(1)
        await logger.awarning(
            "ephemeral_container_not_ready",
            container_id=container_id,
            engine=engine,
            timeout=timeout,
        )
        return False

    async def stop_and_remove(self, container_id: str) -> None:
        """Best-effort container teardown.

        We issue ``docker stop`` then ``docker rm`` separately so a
        partial failure (container already dead, e.g.) doesn't leave a
        zombie row. Errors are logged but not raised -- the sweep task
        treats teardown as fire-and-forget. ``--rm`` on ``docker run``
        means ``rm`` is usually a no-op, but we issue it anyway for
        belt-and-braces.
        """
        for verb in ("stop", "rm"):
            proc = await asyncio.create_subprocess_exec(
                "docker",
                verb,
                container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                await logger.awarning(
                    "ephemeral_container_teardown_error",
                    verb=verb,
                    container_id=container_id,
                    error=stderr.decode().strip(),
                )


# Per-engine health probes invoked via ``docker exec``. Each must exit 0
# only after the DB is fully ready for connections; using a trivial query
# rather than a TCP probe avoids the "TCP open but auth not loaded yet"
# false-positive Postgres / MySQL exhibit on first boot.
_HEALTH_CHECKS: dict[str, list[str]] = {
    "postgresql": ["pg_isready", "-U", "postgres"],
    "mysql": ["mysqladmin", "ping", "-h", "localhost", "--silent"],
    "mongodb": ["mongosh", "--quiet", "--eval", "db.runCommand({ ping: 1 })"],
}
