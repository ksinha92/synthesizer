"""Operational metrics endpoint.

Exposes Prometheus exposition format by default (Accept text/plain or no header)
so a Prometheus scraper can consume it. Falls back to JSON when the client
explicitly asks for application/json — preserves the legacy behavior used by the
admin dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.job import JobModel

router = APIRouter(tags=["monitoring"])

JOB_STATUSES = (
    "pending",
    "running",
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelled",
)


async def _count_jobs_by_status(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in JOB_STATUSES:
        result = await session.execute(
            select(func.count()).select_from(JobModel).where(JobModel.status == status)
        )
        counts[status] = int(result.scalar_one())
    return counts


def _to_prometheus(counts: dict[str, int]) -> str:
    lines = [
        "# HELP datawrangler_jobs_total Background job count by status.",
        "# TYPE datawrangler_jobs_total gauge",
    ]
    for status, count in counts.items():
        lines.append(f'datawrangler_jobs_total{{status="{status}"}} {count}')
    return "\n".join(lines) + "\n"


@router.get("/metrics")
async def get_metrics(
    accept: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    counts = await _count_jobs_by_status(session)

    if accept and "application/json" in accept:
        return {f"jobs_{status}": count for status, count in counts.items()}

    return Response(content=_to_prometheus(counts), media_type="text/plain; version=0.0.4")
