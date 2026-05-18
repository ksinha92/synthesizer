from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.connections import router as connections_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as projects_router
from app.api.v1.synthetic import router as synthetic_router
from app.api.v1.synthetic_file_schemas import router as synthetic_file_schemas_router
from app.api.v1.synthetic_quality import router as synthetic_quality_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.events import router as events_router
from app.api.v1.masking import router as masking_router
from app.api.v1.subsetting import router as subsetting_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.admin import router as admin_router
from app.api.v1.webhooks import admin_router as webhook_admin_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.file_formats import router as file_formats_router
from app.api.v1.privacy_hub import router as privacy_hub_router
from app.api.v1.database_view import router as database_view_router
from app.api.v1.file_schema_view import router as file_schema_view_router
from app.api.v1.file_schema_preview import router as file_schema_preview_router
from app.api.v1.file_schema_relationships import router as file_schema_relationships_router
from app.api.v1.file_schema_mapper import router as file_schema_mapper_router
from app.api.v1.generator_presets import router as generator_presets_router
from app.api.v1.sensitivity_rules import router as sensitivity_rules_router
from app.api.v1.schema_changes import router as schema_changes_router
from app.api.v1.ephemeral import router as ephemeral_router
from app.infrastructure.monitoring.metrics import router as metrics_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(connections_router)
api_router.include_router(discovery_router)
api_router.include_router(synthetic_router)
api_router.include_router(synthetic_file_schemas_router)
api_router.include_router(synthetic_quality_router)
api_router.include_router(masking_router)
api_router.include_router(subsetting_router)
api_router.include_router(workflows_router)
api_router.include_router(compliance_router)
api_router.include_router(jobs_router)
api_router.include_router(events_router)
api_router.include_router(admin_router)
api_router.include_router(webhooks_router)
api_router.include_router(webhook_admin_router)
api_router.include_router(assistant_router)
api_router.include_router(privacy_hub_router)
api_router.include_router(database_view_router)
api_router.include_router(file_schema_view_router)
api_router.include_router(file_schema_preview_router)
api_router.include_router(file_schema_relationships_router)
api_router.include_router(file_schema_mapper_router)
api_router.include_router(generator_presets_router)
api_router.include_router(sensitivity_rules_router)
api_router.include_router(schema_changes_router)
api_router.include_router(ephemeral_router)
api_router.include_router(file_formats_router)
api_router.include_router(metrics_router)
