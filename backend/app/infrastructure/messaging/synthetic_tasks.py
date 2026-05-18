"""Synthetic generation Celery tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=60,
    acks_late=True,
)
def run_generation_task(self, config_id: str, project_id: str, job_id: str):
    """Run synthetic data generation as async Celery task."""
    import asyncio
    asyncio.run(_run_generation_async(self, config_id, project_id, job_id))


async def _run_generation_async(task, config_id: str, project_id: str, job_id: str):
    import uuid
    from sqlalchemy import update

    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.sqlalchemy.synthetic_repo import SQLAlchemySyntheticRepository
    from app.infrastructure.engine.faker_engine import FakerEngine
    from app.infrastructure.messaging.progress_pubsub import publish_progress

    config_uuid = uuid.UUID(config_id)
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

            repo = SQLAlchemySyntheticRepository(session)
            config = await repo.get(config_uuid)
            if not config:
                raise ValueError(f"Synthetic config {config_id} not found")
            if config.source_connection_id is None:
                raise ValueError(
                    f"Synthetic config {config_id} has no source connection — reassign one before re-running"
                )

            seed = config.config.get("seed")
            schema_metadata = {"relationships": []}
            method = config.generation_method if hasattr(config, "generation_method") else config.config.get("generation_method", "faker")

            # Dispatch to appropriate engine based on generation method
            if method in ("copulas", "gaussian_copula", "ctgan", "statistical"):
                from app.infrastructure.engine.statistical_engine import StatisticalEngine
                stat_method = "ctgan" if method == "ctgan" else "gaussian_copula"
                engine = StatisticalEngine(method=stat_method, config=config.config or {})

                # Load source data for statistical training
                source_data = await _load_source_data(session, config)
                schema_metadata["source_data"] = source_data

                result = await engine.generate(config, schema_metadata)

            elif method == "llm":
                from app.infrastructure.engine.llm_engine import LLMEngine
                from app.infrastructure.ai.llm_provider import create_provider
                from app.config import Settings
                llm_settings = Settings()
                llm_provider = create_provider(llm_settings)
                engine = LLMEngine(llm_provider=llm_provider)
                result = await engine.generate(config, schema_metadata)

            else:
                # Default: Faker engine
                engine = FakerEngine(seed=seed)
                result = await engine.generate(config, schema_metadata)

            total_rows = sum(len(rows) for rows in result.values())

            # Update progress before quality evaluation
            await session.execute(
                update(JobModel).where(JobModel.id == job_uuid)
                .values(progress=80)
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 80,
                "result_summary": None,
            })

            # Run quality evaluation if source data is available
            quality_summary = None
            if method in ("copulas", "gaussian_copula", "ctgan", "statistical"):
                try:
                    from app.infrastructure.engine.quality_evaluator import QualityEvaluator
                    import pandas as pd
                    evaluator = QualityEvaluator()
                    source_data = schema_metadata.get("source_data", {})

                    for table_name, synth_rows in result.items():
                        real_df = source_data.get(table_name)
                        if real_df is not None and synth_rows:
                            if not isinstance(real_df, pd.DataFrame):
                                real_df = pd.DataFrame(real_df)
                            synth_df = pd.DataFrame(synth_rows)
                            report = evaluator.evaluate(real_df, synth_df)
                            quality_summary = {
                                "overall_score": report.overall_score,
                                "shape_score": report.shape_score,
                                "pair_score": report.pair_score,
                                "privacy_score": report.privacy_score,
                            }
                            break  # Evaluate first table as representative
                except Exception as qe:
                    await logger.awarning("quality_evaluation_failed", error=str(qe))

            result_summary = {"tables": len(result), "total_rows": total_rows, "method": method}
            if quality_summary:
                result_summary["quality"] = quality_summary

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

            await logger.ainfo(
                "generation_task_completed",
                config_id=config_id, job_id=job_id,
                tables=len(result), total_rows=total_rows, method=method,
            )

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.completed", {"job_id": job_id, "job_type": "synthetic", "tables": len(result), "total_rows": total_rows, "method": method})

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

            await logger.aerror("generation_task_failed", config_id=config_id, job_id=job_id, error=str(exc))

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.failed", {"job_id": job_id, "job_type": "synthetic", "error": str(exc)[:500]})

            raise task.retry(exc=exc)


async def _load_source_data(session, config) -> dict:
    """Load source data from the connection for statistical training."""
    import pandas as pd
    from sqlalchemy import select

    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.connectors.registry import create_registry
    from app.domain.connection.value_objects import ConnectorType
    from app.infrastructure.persistence.sqlalchemy.connection_repo import _decrypt_credentials

    source_data = {}
    conn_id = config.source_connection_id
    if not conn_id:
        return source_data

    result = await session.execute(
        select(ConnectionModel).where(ConnectionModel.id == conn_id)
    )
    conn_model = result.scalar_one_or_none()
    if not conn_model:
        return source_data

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

    tables_config = config.tables or []
    for table_cfg in tables_config:
        table_name = table_cfg.get("table_name", "")
        schema_name = table_cfg.get("schema", "public")
        if table_name:
            try:
                rows = await connector.get_sample_data(schema_name, table_name, limit=50_000)
                if rows:
                    source_data[table_name] = pd.DataFrame(rows)
            except Exception as e:
                logger.warning("source_data_load_failed", table=table_name, error=str(e))

    await connector.close()
    return source_data


# ── File-set generation (Phase 46) ──────────────────────────────────────────
@celery_app.task(bind=True, max_retries=1, default_retry_delay=120, acks_late=True)
def run_file_set_generation_task(self, file_set_dict: dict, project_id: str, job_id: str):
    """Generate every file in a FileSetDefinition; bundle into a zip; update Job."""
    import asyncio as _asyncio
    _asyncio.run(_run_file_set_async(self, file_set_dict, project_id, job_id))


async def _run_file_set_async(task, file_set_dict: dict, project_id: str, job_id: str):
    import tempfile
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    from pathlib import Path as _Path
    from sqlalchemy import update as _update

    from app.config import settings as _settings
    from app.domain.synthetic.file_schema import FileSetDefinition
    from app.infrastructure.engine.file_set_orchestrator import FileSetOrchestrator
    from app.infrastructure.persistence.database import async_session_factory as _factory
    from app.infrastructure.persistence.models.job import JobModel as _JobModel
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.infrastructure.writers.zip_bundler import bundle_files

    job_uuid = _uuid.UUID(job_id)

    async with _factory() as session:
        try:
            # F9: stamp celery_task_id so cancel-by-Celery-ID becomes possible.
            job = await session.get(_JobModel, job_uuid)
            if job and not job.celery_task_id:
                job.celery_task_id = task.request.id

            await session.execute(
                _update(_JobModel).where(_JobModel.id == job_uuid).values(
                    status="running", started_at=_dt.now(_tz.utc)
                )
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 0,
                "result_summary": None,
            })

            file_set = FileSetDefinition.from_dict(file_set_dict)
            row_counts = file_set_dict.get("row_counts") or {}

            # Look up any file-field masking rules the operator wired via
            # the Files tab so generated rows actually honor them. Without
            # this step the rules were stored but never applied — a silent
            # data-leak risk for synthetic outputs that flow downstream.
            #
            # The loader also returns a worker-level skip report
            # (duplicate schema names, etc.) which we thread into the
            # orchestrator so the run-wide skip set is unified.
            masking_rules_by_schema, worker_skips = await _load_file_masking_rules(
                session, project_id, file_set
            )

            storage_root = _Path(getattr(_settings, "STORAGE_PATH", "/tmp/datawrangler-files"))
            bundle_dir = storage_root / "file-sets" / job_id
            bundle_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory(prefix=f"fileset-{job_id}-") as work_dir:
                orch = FileSetOrchestrator(
                    file_set,
                    row_counts=row_counts,
                    masking_rules_by_schema=masking_rules_by_schema,
                    masking_salt=getattr(_settings, "SECRET_KEY", "file-set-default-salt"),
                    initial_masking_skips=worker_skips,
                )
                written = await orch.generate(_Path(work_dir))

                bundle_path = bundle_dir / f"{file_set.name}.zip"
                manifest = {
                    "file_set": file_set.name,
                    "job_id": job_id,
                    "project_id": project_id,
                    "generated_at": _dt.now(_tz.utc).isoformat(),
                    "schema_count": len(file_set.schemas),
                }
                bundle_files(written, manifest, bundle_path)

            # Pull the unified skip report off the orchestrator. The job
            # result_summary carries both the applied count and the skip
            # list so the UI can render "completed with N rules skipped"
            # rather than a misleading bare "completed". A success status
            # combined with a non-empty masking_skipped list is the new
            # signal operators / compliance reviewers look for.
            skip_report = orch.masking_skip_report()
            fs_result_summary = {
                "bundle_path": str(bundle_path),
                "file_count": len(written),
                "file_set_name": file_set.name,
                "masking_applied_count": orch.masking_applied_count(),
                "masking_skipped": skip_report,
            }
            if skip_report:
                await logger.awarning(
                    "file_set_generation_completed_with_skipped_rules",
                    job_id=job_id,
                    skipped_count=len(skip_report),
                    applied_count=orch.masking_applied_count(),
                )
            # Demote to ``completed_with_warnings`` so the UI shows the
            # operator that something needs review — a green "completed"
            # pill while requested masking was silently dropped is the
            # exact failure mode Codex flagged.
            final_status, warning_message = determine_file_set_job_status(
                skip_report
            )
            await session.execute(
                _update(_JobModel).where(_JobModel.id == job_uuid).values(
                    status=final_status,
                    progress=100,
                    completed_at=_dt.now(_tz.utc),
                    result_summary=fs_result_summary,
                    error_message=warning_message,
                )
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": final_status,
                "progress": 100,
                "result_summary": fs_result_summary,
            })

            await logger.ainfo(
                "file_set_generation_completed",
                job_id=job_id, file_count=len(written), bundle=str(bundle_path),
            )
        except Exception as exc:
            await session.rollback()
            async with _factory() as err_session:
                await err_session.execute(
                    _update(_JobModel).where(_JobModel.id == job_uuid).values(
                        status="failed", error_message=str(exc)[:1000]
                    )
                )
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })
            await logger.aerror("file_set_generation_failed", job_id=job_id, error=str(exc))
            raise task.retry(exc=exc)


def build_file_rule_payload(
    field_name: str,
    rule,
    preset,
    schema_id_str: str,
    column_id_to_field: dict[str, tuple[str, str]],
) -> dict:
    """Convert one persisted file-field rule into the orchestrator dict.

    Pure function so the worker's per-rule transformation can be
    exercised without a live DB session. ``rule`` is duck-typed against
    ``MaskingRuleModel`` (ORM attribute access) so the test suite can
    supply ``SimpleNamespace`` mocks.

    Three correctness points the helper has to get right — all of them
    are bugs Codex caught in earlier passes:

    1. ``masking_type`` comes off the ORM row as a plain ``str``. Don't
       call ``.value`` on it; that's the domain entity's shape, not the
       model's.
    2. Joint rules with non-empty ``linked_column_ids`` only reach the
       ``mask_row`` path when BOTH ``linked_column_ids`` and
       ``linked_column_names`` are set on the output dict —
       ``partition_masking_rules`` checks ``linked_column_ids`` to route
       joint, and ``mask_row`` uses ``linked_column_names`` to seed the
       row hash.
    3. Preset overrides: ``generator_type`` wins, ``preset.config`` is
       the base and rule-level config layers on top, and
       ``preset.name`` becomes ``consistency_group`` when
       ``preset.consistency`` is truthy.
    """
    masking_type = (
        preset.generator_type if preset is not None else rule.masking_type
    )
    masking_config = dict(rule.masking_config or {})
    if preset is not None:
        masking_config = {**(preset.config or {}), **masking_config}

    linked_ids = [str(uid) for uid in (rule.linked_column_ids or [])]
    linked_names = resolve_linked_field_names_in_schema(
        linked_ids, schema_id_str, column_id_to_field
    )

    consistency_group = (
        (preset.name if preset and preset.consistency else None)
        or rule.consistency_group
    )

    return {
        "column_name": field_name,
        "masking_type": masking_type,
        "masking_config": masking_config,
        "consistency_group": consistency_group,
        # Both fields populated together: linked_column_ids is what
        # partition_masking_rules inspects to route joint;
        # linked_column_names is what MaskingEngine.mask_row reads to
        # seed the row hash. Dropping either silently demotes the rule
        # into the plain bucket — the exact regression we're guarding
        # against here.
        "linked_column_ids": linked_ids,
        "linked_column_names": linked_names,
    }


def determine_file_set_job_status(
    skip_report: list[dict],
) -> tuple[str, str | None]:
    """Pick the file-set job's terminal status from its skip report.

    Pure function so the "did we silently downgrade an operator's
    request?" decision is unit-testable. Returns
    ``(status, error_message)``. Clean run → ``("completed", None)``.
    Non-empty skip list → ``("completed_with_warnings", "<N> masking…")``.

    The error_message exists so callers that only render ``job.status``
    + ``job.error_message`` (the default UI shape for failed jobs)
    still surface the warning even before they learn about the new
    status pill. Defense in depth — a UI that doesn't recognize the
    new status will still show the message; one that does will show
    both the pill and the message.
    """
    if not skip_report:
        return "completed", None
    n = len(skip_report)
    message = (
        f"{n} masking rule(s) skipped during file-set generation — "
        f"see masking_skipped in result_summary"
    )
    return "completed_with_warnings", message


def index_persisted_schemas(
    schema_rows: list[tuple],
) -> tuple[dict[str, str], dict[str, tuple[str, str]], set[str]]:
    """Bucket persisted schemas by name, build the column-id reverse map,
    and surface duplicate names.

    ``file_schemas.name`` is not unique within a project — the create
    endpoints allow duplicates. When the same name occurs twice the
    worker cannot tell which row the operator meant, so we refuse to
    apply rules for that name at all rather than silently bind to an
    arbitrary id.

    Inputs are tuples of ``(schema_uuid, schema_name, fields_json)`` as
    SQLAlchemy returns them. Pure function so the duplicate-detection
    behavior is unit-testable without spinning up a DB.

    Returns ``(schema_id_by_name, column_id_to_field, duplicate_names)``.
    ``schema_id_by_name`` only contains entries with a unique name; the
    column-id reverse map is built from those same rows so a rule on a
    duplicate-named schema doesn't get linked-name resolution either.
    """
    from app.domain.synthetic.file_schema import file_field_column_id

    seen_count: dict[str, int] = {}
    name_to_id: dict[str, str] = {}
    fields_by_name: dict[str, object] = {}
    for sid, sname, fields in schema_rows:
        seen_count[sname] = seen_count.get(sname, 0) + 1
        if sname not in name_to_id:
            name_to_id[sname] = str(sid)
            fields_by_name[sname] = fields

    duplicate_names = {n for n, c in seen_count.items() if c > 1}
    # Drop ambiguous names: we have no way to pick the right id.
    schema_id_by_name: dict[str, str] = {
        n: sid for n, sid in name_to_id.items() if n not in duplicate_names
    }

    column_id_to_field: dict[str, tuple[str, str]] = {}
    for sname, sid in schema_id_by_name.items():
        for f in (fields_by_name.get(sname) or []):
            fname = f.get("name") if isinstance(f, dict) else None
            if not fname:
                continue
            column_id_to_field[str(file_field_column_id(sid, fname))] = (
                sid,
                fname,
            )
    return schema_id_by_name, column_id_to_field, duplicate_names


def resolve_linked_field_names_in_schema(
    linked_ids: list[str],
    own_schema_id: str,
    column_id_to_field: dict[str, tuple[str, str]],
) -> list[str]:
    """Map synthetic uuid5 column ids back to field names in one schema.

    Joint masking with ``linked_column_ids`` only makes sense within a
    single schema — ``mask_row`` sees one row at a time. Cross-schema
    links are silently dropped rather than raising; the rule degrades to
    "use base row identity for the seed," which is the same outcome a
    rule with no linkage already has.
    """
    names: list[str] = []
    for lid in linked_ids:
        resolved = column_id_to_field.get(lid)
        if resolved is None:
            continue
        schema_id, field_name = resolved
        if schema_id == own_schema_id:
            names.append(field_name)
    return names


async def _load_file_masking_rules(
    session, project_id: str, file_set
) -> tuple[dict[str, list[dict]], list[dict]]:
    """Build {schema_name: [rule_cfg, ...]} + a skip report for the worker.

    Two-step lookup: resolve persisted file_schemas in this project (by
    name) → take their ids → pick masking_rules whose match_pattern
    identifies them as file-field rules (``kind == "file_field"`` +
    ``file_schema_id``). Preset overrides are merged in the same way the
    DB masking task does so generator_type / consistency layer on top of
    the rule row.

    Joint rules with ``linked_column_ids`` need an extra resolution pass:
    each id is a synthetic UUID5 of (schema_id, field_name), so we
    rebuild that mapping for every (schema, field) in scope and look the
    ids up. Without this, joint rules dropped to plain-bucket dispatch
    and lost paired-faker correlation in the generated file.

    Returns ``(rules_by_schema, skip_report)`` where ``skip_report`` is a
    list of ``{schema, column, reason}`` dicts the caller threads into
    the orchestrator so the job's result_summary reflects rules the
    worker refused (e.g. ``duplicate_schema_name``). Without this, the
    job would report success while some operator-requested masking was
    silently dropped.
    """
    import uuid as _uuid
    from sqlalchemy import select as _select

    from app.infrastructure.persistence.models.file_schema import FileSchemaModel
    from app.infrastructure.persistence.models.generator_preset import (
        GeneratorPresetModel,
    )
    from app.infrastructure.persistence.models.masking import (
        MaskingPolicyModel,
        MaskingRuleModel,
    )

    schema_names = [s.name for s in file_set.schemas]
    if not schema_names:
        return {}, []
    skip_report: list[dict] = []

    project_uuid = _uuid.UUID(project_id)
    # Fetch ``fields`` alongside id/name so we can build the synthetic
    # column-id reverse map below without a second query.
    schema_q = await session.execute(
        _select(
            FileSchemaModel.id,
            FileSchemaModel.name,
            FileSchemaModel.fields,
        ).where(
            FileSchemaModel.project_id == project_uuid,
            FileSchemaModel.name.in_(schema_names),
        )
    )
    schema_id_by_name, column_id_to_field, duplicate_names = (
        index_persisted_schemas(list(schema_q.all()))
    )
    for dup in duplicate_names:
        # ``file_schemas.name`` is not unique within a project. When the
        # operator's file_set names a schema that resolves to multiple
        # rows, we have no way to pick the right id without a hint —
        # log AND surface in the skip report so the job's
        # result_summary reflects that this schema's rules were dropped.
        reason = (
            "duplicate_schema_name: multiple persisted file_schemas share "
            "this name; cannot determine which one the rule applies to"
        )
        skip_report.append({"schema": dup, "column": None, "reason": reason})
        await logger.awarning(
            "file_set_duplicate_schema_name",
            schema=dup,
            project_id=project_id,
            reason=reason,
        )
    if not schema_id_by_name:
        return {}, skip_report

    schema_ids = list(schema_id_by_name.values())
    rules_q = await session.execute(
        _select(MaskingRuleModel)
        .join(
            MaskingPolicyModel,
            MaskingPolicyModel.id == MaskingRuleModel.policy_id,
        )
        .where(
            MaskingPolicyModel.project_id == project_uuid,
            MaskingRuleModel.match_pattern["kind"].astext == "file_field",
            MaskingRuleModel.match_pattern["file_schema_id"].astext.in_(schema_ids),
        )
    )
    rules = list(rules_q.scalars().all())
    if not rules:
        return {}, skip_report

    preset_ids = [r.preset_id for r in rules if r.preset_id is not None]
    presets: dict = {}
    if preset_ids:
        preset_q = await session.execute(
            _select(GeneratorPresetModel).where(
                GeneratorPresetModel.id.in_(preset_ids)
            )
        )
        for p in preset_q.scalars().all():
            presets[p.id] = p

    name_by_schema_id = {sid: name for name, sid in schema_id_by_name.items()}
    out: dict[str, list[dict]] = {}
    for r in rules:
        mp = r.match_pattern or {}
        schema_id_str = mp.get("file_schema_id")
        field_name = mp.get("field_name")
        if not schema_id_str or not field_name:
            continue
        schema_name = name_by_schema_id.get(schema_id_str)
        if not schema_name:
            continue

        preset = presets.get(r.preset_id) if r.preset_id else None
        out.setdefault(schema_name, []).append(
            build_file_rule_payload(
                field_name, r, preset, schema_id_str, column_id_to_field
            )
        )
    return out, skip_report
