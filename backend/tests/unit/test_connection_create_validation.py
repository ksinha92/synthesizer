"""Pydantic validation tests for the ConnectionCreate request model.

The model is the public API contract — it has to reject bad input *before*
anything hits the database or driver. We validate the rules the audit
flagged as missing: port range, unknown connector types, empty database.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.connections import ConnectionCreate


def _valid_payload(**overrides):
    base = {
        "name": "Prod replica",
        "connector_type": "postgresql",
        "host": "db.example.com",
        "port": 5432,
        "database_name": "ameritas",
        "username": "svc_dw",
        "password": "x",
    }
    base.update(overrides)
    return base


class TestPortRange:
    def test_port_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(port=0))

    def test_port_too_high_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(port=70000))

    def test_port_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(port=-5))


class TestConnectorType:
    @pytest.mark.parametrize(
        "ct",
        ["postgresql", "mysql", "mongodb", "snowflake", "oracle", "sqlserver", "redshift", "databricks", "db2"],
    )
    def test_all_nine_supported_types_accepted(self, ct: str) -> None:
        ConnectionCreate(**_valid_payload(connector_type=ct))

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(connector_type="cassandra"))


class TestRequiredFields:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(name=""))

    def test_empty_database_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionCreate(**_valid_payload(database_name=""))

    def test_extra_params_defaults_to_empty_dict(self) -> None:
        c = ConnectionCreate(**_valid_payload())
        assert c.extra_params == {}
