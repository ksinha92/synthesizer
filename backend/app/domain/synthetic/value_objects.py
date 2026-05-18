"""Synthetic value objects. No framework dependencies."""

from enum import Enum


class GenerationMethod(str, Enum):
    FAKER = "faker"
    STATISTICAL = "statistical"
    LLM = "llm"


class EngineType(str, Enum):
    FAKER = "faker"
    GAUSSIAN_COPULA = "gaussian_copula"
    CTGAN = "ctgan"
    LLM_NLP = "llm_nlp"


class FileFormat(str, Enum):
    CSV = "csv"
    FIXED_WIDTH = "fixed_width"
    VSAM_FIXED = "vsam_fixed"
    VSAM_VARIABLE = "vsam_variable"
    PARQUET = "parquet"
    ORC = "orc"


class EncodingType(str, Enum):
    ASCII = "ascii"
    EBCDIC_CP037 = "ebcdic_cp037"
    EBCDIC_CP1140 = "ebcdic_cp1140"
    UTF8 = "utf8"


class CompType(str, Enum):
    NONE = "none"
    COMP = "comp"
    COMP_3 = "comp_3"
