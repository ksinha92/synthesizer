"""Discovery value objects. No framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.shared.value_object import ValueObject


class PIIType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PERSON_NAME = "person_name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    MEDICAL_RECORD = "medical_record"
    FINANCIAL_ACCOUNT = "financial_account"
    OTHER = "other"
    NONE = "none"


class Classification(str, Enum):
    AUTO_CLASSIFIED = "auto_classified"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_CLASSIFIED = "manually_classified"
    DISMISSED = "dismissed"


class RelationshipType(str, Enum):
    FOREIGN_KEY = "foreign_key"
    INFERRED_NAMING = "inferred_naming"
    INFERRED_OVERLAP = "inferred_overlap"
    INFERRED_LLM = "inferred_llm"


@dataclass(frozen=True)
class PIIConfidence(ValueObject):
    """Weighted confidence score from the detection pipeline."""

    score: float = 0.0
    detector: str = ""  # Which layer(s) detected: "regex", "presidio", "heuristic", "llm"
    details: dict = field(default_factory=dict)
