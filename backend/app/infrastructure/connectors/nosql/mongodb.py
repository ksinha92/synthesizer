"""MongoDB connector using motor (async PyMongo) with document-sampling schema inference."""

from __future__ import annotations

import asyncio
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5000  # ms (motor uses ms)
INTROSPECTION_TIMEOUT = 30.0  # seconds
DEFAULT_SAMPLE_SIZE = 100
DEFAULT_MAX_DEPTH = 2
MAX_DOC_SIZE_BYTES = 1_000_000  # 1MB — skip larger docs
MAX_TOTAL_SAMPLE_BYTES = 50_000_000  # 50MB — stop sampling

# Python type → SQL-like type mapping
_TYPE_MAP = {
    str: "varchar",
    int: "integer",
    float: "double",
    bool: "boolean",
    datetime: "timestamp",
    list: "jsonb",
    dict: "jsonb",
    ObjectId: "uuid",
    bytes: "bytea",
}


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


class MongoDBConnector(BaseConnector):
    """MongoDB connector with document-sampling schema inference."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sample_size = int(self._extra_params.get("max_sample_size") or DEFAULT_SAMPLE_SIZE)
        self._max_depth = int(self._extra_params.get("max_doc_depth") or DEFAULT_MAX_DEPTH)
        # Defer client construction to first use — the Motor/PyMongo client
        # validates credentials eagerly in __init__, which makes the
        # connector itself untestable in isolation (e.g. unit tests for
        # _build_client_kwargs would need a full credential triple just to
        # construct the object).
        self._client: AsyncIOMotorClient | None = None

    def _get_client(self) -> AsyncIOMotorClient:
        if self._client is None:
            self._client = AsyncIOMotorClient(self._build_uri(), **self._build_client_kwargs())
        return self._client

    def _build_uri(self) -> str:
        if self._username:
            auth = f"{quote_plus(self._username)}:{quote_plus(self._password)}@"
        else:
            auth = ""
        return f"mongodb://{auth}{self._host}:{self._port}"

    def _build_client_kwargs(self) -> dict[str, Any]:
        # Bound the per-client pool so a misconfigured tenant can't open 50
        # sockets against a shared cluster (motor default). Overridable from
        # the UI via ``mongo_max_pool_size`` / ``mongo_min_pool_size``.
        kwargs: dict[str, Any] = {
            "serverSelectionTimeoutMS": CONNECTION_TIMEOUT,
            "maxPoolSize": int(self._extra_params.get("mongo_max_pool_size") or 20),
            "minPoolSize": int(self._extra_params.get("mongo_min_pool_size") or 0),
            "socketTimeoutMS": int(self._extra_params.get("mongo_socket_timeout_ms") or 60_000),
            "connectTimeoutMS": int(self._extra_params.get("mongo_connect_timeout_ms") or CONNECTION_TIMEOUT),
        }
        if self._extra_params.get("ssl"):
            kwargs["tls"] = True
            if self._extra_params.get("ssl_trust_server_cert"):
                kwargs["tlsAllowInvalidCertificates"] = True
            if ca := self._extra_params.get("ssl_ca_cert_path"):
                kwargs["tlsCAFile"] = ca
        # Resolve auth mechanism — explicit ``auth_mechanism`` wins, else
        # we map ``auth_mode`` (which the UI sends) to MongoDB's canonical
        # mechanism strings.
        mechanism = self._extra_params.get("auth_mechanism")
        if not mechanism:
            mode = self._extra_params.get("auth_mode")
            mechanism = {
                "scram_sha_256": "SCRAM-SHA-256",
                "scram_sha_1": "SCRAM-SHA-1",
                "x509": "MONGODB-X509",
                "gssapi": "GSSAPI",
                "aws": "MONGODB-AWS",
            }.get(mode or "")
        if mechanism:
            kwargs["authMechanism"] = mechanism

        # MONGODB-X509: cert auth — username is derived from the cert
        # subject, so we pass the client cert/key via tls.
        if mechanism == "MONGODB-X509":
            if not (
                self._extra_params.get("ssl_client_cert_path")
                and self._extra_params.get("ssl_client_key_path")
            ):
                raise ValueError(
                    "MongoDB X.509 auth requires both ssl_client_cert_path and "
                    "ssl_client_key_path (the client certificate)."
                )
            kwargs["tls"] = True
            kwargs["tlsCertificateKeyFile"] = self._extra_params["ssl_client_cert_path"]
            # ``authSource`` for X.509 is always $external.
            kwargs["authSource"] = "$external"
        elif mechanism == "GSSAPI":
            # Kerberos — driver picks up TGT from KRB5CCNAME at connect time.
            # Requires ``motor[gssapi]`` extras / pykerberos to be installed.
            kwargs["authSource"] = "$external"
            if service_name := self._extra_params.get("gssapi_service_name"):
                kwargs["authMechanismProperties"] = f"SERVICE_NAME:{service_name}"
        elif mechanism == "MONGODB-AWS":
            # AWS IAM — credentials come from the standard boto3 chain.
            kwargs["authSource"] = "$external"
            if session_token := self._extra_params.get("aws_session_token"):
                kwargs["authMechanismProperties"] = f"AWS_SESSION_TOKEN:{session_token}"
        else:
            if auth_source := self._extra_params.get("auth_source"):
                kwargs["authSource"] = auth_source

        if replica_set := self._extra_params.get("replica_set"):
            kwargs["replicaSet"] = replica_set
        return kwargs

    async def test_connection(self) -> bool:
        try:
            async with asyncio.timeout(5.0):
                await self._get_client().admin.command("ping")
                return True
        except Exception as e:
            await logger.awarning("connector_test_failed", connector="mongodb", error=_sanitize_error(str(e)))
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            db_names = await self._get_client().list_database_names()
            filtered = [n for n in db_names if n not in ("admin", "local", "config")]
            schemas = [{"name": n} for n in sorted(filtered)]
            if allow is not None:
                allowed = {s.lower() for s in allow}
                schemas = [s for s in schemas if s["name"].lower() in allowed]
            return schemas

    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            db = self._get_client()[schema]
            collections = await db.list_collection_names()
            result = []
            for coll_name in sorted(collections):
                try:
                    count = await db[coll_name].estimated_document_count()
                except Exception:
                    count = 0
                result.append({"name": coll_name, "row_count": count, "size_bytes": 0})
            return result

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            db = self._get_client()[schema]
            collection = db[table]

            # Sample documents with size guard
            field_types: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            field_nullable: dict[str, bool] = defaultdict(lambda: False)
            total_bytes = 0
            sampled = 0

            cursor = collection.find().limit(self._sample_size)
            async for doc in cursor:
                # Size guard
                doc_size = sys.getsizeof(str(doc))
                if doc_size > MAX_DOC_SIZE_BYTES:
                    await logger.awarning("mongodb_doc_skipped", collection=table, size=doc_size)
                    continue
                total_bytes += doc_size
                if total_bytes > MAX_TOTAL_SAMPLE_BYTES:
                    await logger.awarning("mongodb_sampling_capped", collection=table, total_bytes=total_bytes)
                    break

                sampled += 1
                flat = _flatten_doc(doc, max_depth=self._max_depth)
                all_keys = set(field_types.keys()) | set(flat.keys())

                for key in flat:
                    val = flat[key]
                    py_type = type(val)
                    type_name = _TYPE_MAP.get(py_type, "varchar")
                    field_types[key][type_name] += 1

                # Track nullability (field missing in this doc)
                for key in all_keys:
                    if key not in flat:
                        field_nullable[key] = True

            # Build column metadata. When a field's sampled values disagree on
            # type (e.g. some docs store ``age`` as int, others as str), we
            # surface the full distribution under ``mixed_types`` so the
            # Database View can render a badge — the SQL-flavored
            # ``data_type`` only carries one winner, which would otherwise
            # silently hide schema drift.
            columns = []
            for field_name, types in sorted(field_types.items()):
                # ``max`` ties go to whichever key Python's hash visits first,
                # which is fine because the badge always lists every observed
                # type. Sort the type breakdown for deterministic responses.
                most_common_type = max(types, key=types.get)
                type_breakdown = dict(sorted(types.items()))
                col: dict[str, Any] = {
                    "name": field_name,
                    "data_type": most_common_type,
                    "is_nullable": field_nullable.get(field_name, False),
                    "is_primary_key": field_name == "_id",
                    "is_foreign_key": False,
                    "fk_references": None,
                    "character_maximum_length": None,
                    "numeric_precision": None,
                }
                if len(type_breakdown) > 1:
                    # Carry both the per-field breakdown and a flat list of
                    # observed types in ``stats`` so the discovery repository
                    # can persist them without a new column.
                    col["stats"] = {
                        "mixed_types": list(type_breakdown.keys()),
                        "type_breakdown": type_breakdown,
                    }
                columns.append(col)

            return columns

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            db = self._get_client()[schema]
            collection = db[table]
            rows = []
            cursor = collection.find().limit(min(limit, 1000))
            async for doc in cursor:
                flat = _flatten_doc(doc, max_depth=self._max_depth)
                # Serialize ObjectId to string
                for k, v in flat.items():
                    if isinstance(v, ObjectId):
                        flat[k] = str(v)
                rows.append(flat)
            return rows

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _flatten_doc(doc: dict, prefix: str = "", max_depth: int = 2, current_depth: int = 0) -> dict:
    """Flatten nested MongoDB document to dot notation, capped at max_depth."""
    flat = {}
    for key, value in doc.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict) and current_depth < max_depth:
            flat.update(_flatten_doc(value, full_key, max_depth, current_depth + 1))
        else:
            flat[full_key] = value
    return flat
