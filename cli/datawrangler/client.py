"""DataWrangler API client for CLI."""

from __future__ import annotations

import os
import time

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn


class DataWranglerClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("DATAWRANGLER_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.environ.get("DATAWRANGLER_API_KEY", "")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=30.0,
        )

    def _get_token(self) -> str:
        if not self.api_key:
            return ""
        resp = httpx.post(f"{self.base_url}/api/v1/auth/token", json={"api_key": self.api_key}, timeout=10.0)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def discover(self, project_id: str, connection_id: str) -> str:
        resp = self._client.post(f"/api/v1/projects/{project_id}/discovery/run", json={"connection_id": connection_id})
        resp.raise_for_status()
        return resp.json()["job_id"]

    def mask(self, project_id: str, policy_id: str, connection_id: str) -> str:
        resp = self._client.post(f"/api/v1/projects/{project_id}/masking/execute", json={"policy_id": policy_id, "connection_id": connection_id})
        resp.raise_for_status()
        return resp.json()["job_id"]

    def generate(self, project_id: str, config_id: str) -> str:
        resp = self._client.post(f"/api/v1/projects/{project_id}/synthetic/generate", json={"config_id": config_id})
        resp.raise_for_status()
        return resp.json()["job_id"]

    def subset(self, project_id: str, config_id: str) -> str:
        resp = self._client.post(f"/api/v1/projects/{project_id}/subset/execute", json={"config_id": config_id})
        resp.raise_for_status()
        return resp.json()["job_id"]

    def workflow_run(self, project_id: str, workflow_id: str) -> str:
        resp = self._client.post(f"/api/v1/projects/{project_id}/workflows/{workflow_id}/execute")
        resp.raise_for_status()
        return resp.json()["job_id"]

    def get_job(self, project_id: str, job_id: str) -> dict:
        resp = self._client.get(f"/api/v1/projects/{project_id}/jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def list_jobs(self, project_id: str) -> list[dict]:
        resp = self._client.get(f"/api/v1/projects/{project_id}/jobs?page_size=20")
        resp.raise_for_status()
        return resp.json()["items"]

    def poll_job(self, project_id: str, job_id: str, interval: int = 5, timeout: int = 1800) -> dict:
        """Poll job until terminal status. Shows rich progress bar."""
        start = time.monotonic()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%")) as progress:
            task = progress.add_task(f"Job {job_id[:8]}...", total=100)
            while True:
                if time.monotonic() - start > timeout:
                    raise TimeoutError(f"Job polling timed out after {timeout}s")
                job = self.get_job(project_id, job_id)
                progress.update(task, completed=job.get("progress", 0), description=f"[{job['status']}] {job['job_type']}")
                if job["status"] in ("completed", "failed", "cancelled"):
                    return job
                time.sleep(interval)
