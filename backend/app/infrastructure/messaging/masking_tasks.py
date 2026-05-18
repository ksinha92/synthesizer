"""Masking Celery tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()

CHUNK_SIZE = 10_000


# Strategies that require the entire column at once. SHUFFLE permutes values;
# any future strategy with similar semantics belongs here. These never run
# through mask_row.
COLUMN_ONLY_MASKING_STRATEGIES: frozenset[str] = frozenset({"shuffle"})


def select_applicable_rules(
    rule_configs: list[dict],
    schema_name: str,
    table_name: str,
    column_names: list[str],
    column_lookup: dict[str, tuple[str, str, str]],
) -> list[dict]:
    """Pick rules that target this table's columns.

    Pure helper extracted from ``_run_masking_async`` so dispatch can be
    exercised in unit tests without a live connector. Two paths:

    - ``column_id`` rules resolve via ``column_lookup`` (built by joining
      ``masking_rules.column_id`` against ``discovered_columns``).
    - ``match_pattern`` rules are regex-matched against column names.

    Guards on the regex path:

    1. File-schema rules carry ``match_pattern.kind == "file_field"`` so
       the file viewer's "Apply rule" can route the rule back to a field
       at synthetic-generation time. Those rules MUST NOT participate in
       DB masking — otherwise the regex fallback below falls through to
       an empty pattern (no ``pattern`` key) and silently masks every
       column in every table.
    2. Likewise, an explicit empty ``pattern`` matches every column. Skip
       it rather than mask the entire database.
    """
    import re

    applicable: list[dict] = []
    for rc in rule_configs:
        mp = rc.get("match_pattern")
        if mp:
            if isinstance(mp, dict) and mp.get("kind") == "file_field":
                continue
            pattern = mp.get("pattern", "") if isinstance(mp, dict) else mp
            if not pattern:
                continue
            for col_name in column_names:
                try:
                    if re.search(pattern, col_name, re.IGNORECASE):
                        applicable.append({**rc, "column_name": col_name})
                except re.error:
                    continue
        elif rc.get("column_id"):
            resolved = column_lookup.get(rc["column_id"])
            if resolved is None:
                continue
            rsname, rtname, rcolname = resolved
            if rsname == schema_name and rtname == table_name and rcolname in column_names:
                applicable.append({**rc, "column_name": rcolname})
    return applicable


def partition_masking_rules(
    applicable_rules: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split rules by required execution model.

    Pure function — extracted so the dispatch behavior can be unit-tested
    without spinning up a real connector. Returns
    ``(column_only_rules, plain_rules, joint_rules)``:

    - ``column_only_rules`` need to see every value at once (SHUFFLE). They
      always run through ``MaskingEngine.mask_column``. consistency_group /
      linked_column_ids on them are meaningless.
    - ``joint_rules`` declare ``consistency_group`` or ``linked_column_ids``
      themselves → run through ``MaskingEngine.mask_row`` so the joint
      semantics actually apply.
    - ``plain_rules`` are everything else → run through ``mask_column``
      independently. Critical: a plain rule's output is determined only by
      its own fields. It must not get re-routed to the row path because a
      sibling rule happens to be joint.
    """
    column_only: list[dict] = []
    joint: list[dict] = []
    plain: list[dict] = []
    for r in applicable_rules:
        if r.get("masking_type") in COLUMN_ONLY_MASKING_STRATEGIES:
            column_only.append(r)
        elif r.get("consistency_group") or r.get("linked_column_ids"):
            joint.append(r)
        else:
            plain.append(r)
    return column_only, plain, joint


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, retry_backoff=True, acks_late=True)
def run_masking_task(self, policy_id: str, connection_id: str, project_id: str, job_id: str):
    """Run masking in 10K row chunks."""
    import asyncio
    asyncio.run(_run_masking_async(self, policy_id, connection_id, project_id, job_id))


async def _run_masking_async(task, policy_id, connection_id, project_id, job_id):
    import uuid
    from sqlalchemy import select, update

    from app.config import settings
    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.persistence.sqlalchemy.masking_repo import SQLAlchemyMaskingRepository
    from app.infrastructure.connectors.registry import create_registry
    from app.infrastructure.engine.masking_engine import MaskingEngine
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.domain.connection.value_objects import ConnectorType
    from app.infrastructure.persistence.sqlalchemy.connection_repo import _decrypt_credentials

    policy_uuid = uuid.UUID(policy_id)
    conn_uuid = uuid.UUID(connection_id)
    job_uuid = uuid.UUID(job_id)

    async with async_session_factory() as session:
        try:
            # F9: stamp celery_task_id so cancel-by-Celery-ID becomes possible.
            job = await session.get(JobModel, job_uuid)
            if job and not job.celery_task_id:
                job.celery_task_id = task.request.id

            await session.execute(
                update(JobModel).where(JobModel.id == job_uuid)
                .values(status="running", started_at=datetime.now(timezone.utc))
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 0,
                "result_summary": None,
            })

            # Load masking policy and rules
            masking_repo = SQLAlchemyMaskingRepository(session)
            policy = await masking_repo.get(policy_uuid)
            if not policy:
                raise ValueError(f"Masking policy {policy_id} not found")

            rules = await masking_repo.get_rules_by_policy(policy_uuid)
            if not rules:
                raise ValueError(f"No rules found for policy {policy_id}")

            # Load source connection
            result = await session.execute(
                select(ConnectionModel).where(ConnectionModel.id == conn_uuid)
            )
            conn_model = result.scalar_one_or_none()
            if not conn_model:
                raise ValueError(f"Connection {connection_id} not found")

            creds = _decrypt_credentials(conn_model.credentials or {})
            registry = create_registry()
            connector = registry.get_connector(
                connector_type=ConnectorType(conn_model.connector_type),
                host=conn_model.host,
                port=conn_model.port,
                database_name=conn_model.database_name,
                username=creds.get("username", ""),
                password=creds.get("password", ""),
                extra_params=conn_model.extra_params,
            )

            # Initialize masking engine
            salt = settings.SECRET_KEY
            engine = MaskingEngine(salt=salt)

            # Phase 56-04: pre-load any generator presets referenced by these
            # rules so masking_type / config are sourced from the preset rather
            # than the rule's own (possibly empty) fields. Without this, presets
            # are metadata-only at masking time.
            preset_ids = [
                getattr(r, "preset_id", None) for r in rules
                if getattr(r, "preset_id", None) is not None
            ]
            preset_lookup: dict = {}
            if preset_ids:
                from app.infrastructure.persistence.models.generator_preset import (
                    GeneratorPresetModel,
                )
                preset_q = await session.execute(
                    select(GeneratorPresetModel).where(
                        GeneratorPresetModel.id.in_(preset_ids)
                    )
                )
                for p in preset_q.scalars().all():
                    preset_lookup[p.id] = p

            # Build rule config list — preset overrides take precedence, and
            # consistency_group + linked_column_ids are carried through so the
            # engine's joint-masking path can use them.
            rule_configs = []
            for rule in rules:
                preset = preset_lookup.get(getattr(rule, "preset_id", None))
                masking_type = (
                    preset.generator_type if preset is not None else rule.masking_type.value
                )
                masking_config = dict(rule.masking_config or {})
                if preset is not None:
                    # Preset config wins; rule-level overrides layer on top.
                    masking_config = {**(preset.config or {}), **masking_config}

                rule_configs.append({
                    "column_id": str(rule.column_id) if rule.column_id else None,
                    "match_pattern": rule.match_pattern,
                    "masking_type": masking_type,
                    "masking_config": masking_config,
                    "preserve_format": rule.preserve_format,
                    "deterministic": rule.deterministic,
                    "preset_id": str(getattr(rule, "preset_id", None)) if getattr(rule, "preset_id", None) else None,
                    "consistency_group": (
                        preset.name if preset and preset.consistency else None
                    ) or getattr(rule, "consistency_group", None),
                    "linked_column_ids": [
                        str(uid) for uid in (getattr(rule, "linked_column_ids", None) or [])
                    ],
                })

            # Discover schemas and apply masking per table
            try:
                schemas = await connector.get_schemas()
            except Exception:
                schemas = ["public"]

            tables_processed = 0
            total_rules = len(rule_configs)

            # Phase 56-04: column_id-based rules (the kind Database View and
            # Privacy Hub create) need a column-name lookup. The previous task
            # only considered match_pattern rules — column_id rules were
            # silently dropped, so the entire Database View → Apply path
            # produced zero masking. Resolve column_id → (schema, table, name)
            # once up front.
            from sqlalchemy import select as _select2
            from app.infrastructure.persistence.models.discovery import (
                DiscoveredColumnModel,
                DiscoveredSchemaModel,
                DiscoveredTableModel,
            )

            col_ids_in_rules = [
                rule.column_id for rule in rules if rule.column_id is not None
            ]
            column_lookup: dict = {}  # column_id → (schema_name, table_name, column_name)
            if col_ids_in_rules:
                col_q = await session.execute(
                    _select2(
                        DiscoveredColumnModel.id,
                        DiscoveredSchemaModel.schema_name,
                        DiscoveredTableModel.table_name,
                        DiscoveredColumnModel.column_name,
                    )
                    .join(
                        DiscoveredTableModel,
                        DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
                    )
                    .join(
                        DiscoveredSchemaModel,
                        DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
                    )
                    .where(DiscoveredColumnModel.id.in_(col_ids_in_rules))
                )
                for cid, sname, tname, cname in col_q.all():
                    column_lookup[str(cid)] = (sname, tname, cname)

            for schema_name in schemas:
                try:
                    tables = await connector.get_tables(schema_name)
                except Exception:
                    continue

                for table_info in tables:
                    table_name = table_info.get("name", table_info) if isinstance(table_info, dict) else table_info

                    try:
                        columns = await connector.get_columns(schema_name, table_name)
                        column_names = [c.get("name", c) if isinstance(c, dict) else c for c in columns]

                        # Find applicable rules for this table's columns
                        # via the pure helper so the empty-pattern and
                        # file-field-rule guards are exercised by tests.
                        applicable_rules = select_applicable_rules(
                            rule_configs,
                            schema_name,
                            table_name,
                            column_names,
                            column_lookup,
                        )

                        if not applicable_rules:
                            continue

                        # Fetch data in chunks and apply masking
                        rows = await connector.get_sample_data(schema_name, table_name, limit=CHUNK_SIZE)
                        if not rows:
                            continue

                        # Phase 56-04: partition rules by their *own* execution
                        # requirements — see partition_masking_rules docstring.
                        from app.domain.masking.value_objects import MaskingStrategy

                        column_only_rules, plain_rules, joint_rules = partition_masking_rules(
                            applicable_rules
                        )

                        def _apply_column_wise(rule_cfg: dict) -> None:
                            col_name = rule_cfg["column_name"]
                            strategy = MaskingStrategy(rule_cfg["masking_type"])
                            col_values = [row.get(col_name) for row in rows]
                            masked_values = engine.mask_column(
                                col_values, strategy, rule_cfg.get("masking_config")
                            )
                            for i, row in enumerate(rows):
                                if col_name in row:
                                    row[col_name] = masked_values[i]

                        for rule_cfg in column_only_rules:
                            if rule_cfg.get("consistency_group") or rule_cfg.get("linked_column_ids"):
                                await logger.awarning(
                                    "masking_rule_consistency_ignored",
                                    column=rule_cfg["column_name"],
                                    strategy=rule_cfg["masking_type"],
                                    reason="column-only strategy ignores consistency_group / linked_column_ids",
                                )
                            _apply_column_wise(rule_cfg)

                        for rule_cfg in plain_rules:
                            _apply_column_wise(rule_cfg)

                        if joint_rules:
                            # Resolve each rule's ``linked_column_ids`` → list of
                            # column names that live in *this* table. Cross-table
                            # links would be meaningless for ``mask_row`` (it
                            # only sees this row), so we filter by (schema, table)
                            # matching the column under mask. The result feeds
                            # ``MaskingEngine.mask_row`` so paired faker outputs
                            # (e.g. linked city/state) actually correlate.
                            def _resolve_linked_names(linked_ids: list) -> list[str]:
                                names: list[str] = []
                                for cid in linked_ids or []:
                                    resolved = column_lookup.get(str(cid))
                                    if resolved is None:
                                        continue
                                    rsname, rtname, rcolname = resolved
                                    if (
                                        rsname == schema_name
                                        and rtname == table_name
                                        and rcolname in column_names
                                    ):
                                        names.append(rcolname)
                                return names

                            row_rules = [
                                {
                                    "column_name": r["column_name"],
                                    "masking_type": r["masking_type"],
                                    "masking_config": r.get("masking_config", {}),
                                    "consistency_group": r.get("consistency_group"),
                                    "linked_column_names": _resolve_linked_names(
                                        r.get("linked_column_ids") or []
                                    ),
                                }
                                for r in joint_rules
                            ]
                            for i, row in enumerate(rows):
                                rows[i] = engine.mask_row(row, row_rules)

                        tables_processed += 1

                    except Exception as e:
                        await logger.awarning("masking_table_error", table=table_name, error=str(e))
                        continue

                    # Update progress
                    progress = min(90, int(tables_processed * 90 / max(len(tables), 1)))
                    await session.execute(
                        update(JobModel).where(JobModel.id == job_uuid)
                        .values(progress=progress)
                    )
                    await session.commit()
                    publish_progress(str(job_uuid), {
                        "status": "running",
                        "progress": progress,
                        "result_summary": None,
                    })

            await connector.close()

            # Mark complete
            result_summary = {"tables_processed": tables_processed, "rules_applied": total_rules}
            await session.execute(
                update(JobModel).where(JobModel.id == job_uuid)
                .values(
                    status="completed", progress=100,
                    completed_at=datetime.now(timezone.utc),
                    result_summary=result_summary,
                )
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "completed",
                "progress": 100,
                "result_summary": result_summary,
            })

            await logger.ainfo("masking_task_completed", policy_id=policy_id, job_id=job_id, tables=tables_processed)

            # Fire webhook
            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.completed", {"job_id": job_id, "job_type": "masking", "tables_processed": tables_processed})

        except Exception as exc:
            await session.rollback()
            async with async_session_factory() as err_session:
                await err_session.execute(
                    update(JobModel).where(JobModel.id == job_uuid)
                    .values(status="failed", error_message=str(exc)[:1000])
                )
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })
            await logger.aerror("masking_task_failed", policy_id=policy_id, job_id=job_id, error=str(exc))

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.failed", {"job_id": job_id, "job_type": "masking", "error": str(exc)[:500]})

            raise task.retry(exc=exc)
