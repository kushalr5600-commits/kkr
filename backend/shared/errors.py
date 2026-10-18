"""BLACKBOX failure taxonomy (Agent manual v4, Part 17) and error semantics.

Every raised ``BlackboxError`` carries a taxonomy code, the owning agent and a
recovery action so the diagnostics layer can log them uniformly.
"""
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    E001 = "E001"  # INPUT
    E002 = "E002"  # SCHEMA
    E003 = "E003"  # GATE
    E004 = "E004"  # MODEL
    E005 = "E005"  # SIM
    E006 = "E006"  # FRAGILITY
    E007 = "E007"  # CERT
    E008 = "E008"  # API
    E009 = "E009"  # UI
    E010 = "E010"  # DEP
    E011 = "E011"  # S390X
    E012 = "E012"  # DATA_LEAK
    E013 = "E013"  # CONTRACT_CHANGE
    E014 = "E014"  # ACCESS


# code -> (category, first owner)
ERROR_CATALOG: dict[ErrorCode, tuple[str, str]] = {
    ErrorCode.E001: ("INPUT", "boundary owner"),
    ErrorCode.E002: ("SCHEMA", "shared contract owner"),
    ErrorCode.E003: ("GATE", "P3"),
    ErrorCode.E004: ("MODEL", "P3"),
    ErrorCode.E005: ("SIM", "P2"),
    ErrorCode.E006: ("FRAGILITY", "P2"),
    ErrorCode.E007: ("CERT", "P4"),
    ErrorCode.E008: ("API", "P4"),
    ErrorCode.E009: ("UI", "P4"),
    ErrorCode.E010: ("DEP", "environment owner"),
    ErrorCode.E011: ("S390X", "P4 + owning component"),
    ErrorCode.E012: ("DATA_LEAK", "P3"),
    ErrorCode.E013: ("CONTRACT_CHANGE", "human"),
    ErrorCode.E014: ("ACCESS", "human"),
}

_DEFAULT_RECOVERY = {
    ErrorCode.E001: "return an HTTP validation error; do not run business logic",
    ErrorCode.E002: "stop integration; fix the interface owner (contract mismatch)",
    ErrorCode.E003: "run the gate unit tests; check M/D/A/U normalization in order",
    ErrorCode.E004: "check model fit/inference; consider BLACKBOX_MODEL_BACKEND=numpy",
    ErrorCode.E005: "run the simulation unit tests; reproduce with the demo transaction",
    ErrorCode.E006: "run the fragility unit tests; check predicate monotonicity",
    ErrorCode.E007: "run the certificate unit tests; degrade to a REVIEW certificate",
    ErrorCode.E008: "inspect the trace_id and first failing stage",
    ErrorCode.E009: "check request lifecycle, loading flag and response replacement",
    ErrorCode.E010: "run the compatibility checks; apply the approved fallback",
    ErrorCode.E011: "classify as environment first; do not rewrite application logic",
    ErrorCode.E012: "discard results; re-run with calibration-only fitting",
    ErrorCode.E013: "write CONTRACT_CHANGE_REQUEST.md and get a human decision",
    ErrorCode.E014: "human must repair credentials/network/account access",
}


class BlackboxError(Exception):
    """Base class. Subclasses fix ``code``; callers may override the rest."""

    code: ErrorCode = ErrorCode.E008

    def __init__(
        self,
        message: str,
        *,
        owner: str | None = None,
        recovery_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.owner = owner or ERROR_CATALOG[self.code][1]
        self.recovery_action = recovery_action or _DEFAULT_RECOVERY[self.code]

    @property
    def category(self) -> str:
        return ERROR_CATALOG[self.code][0]

    def as_dict(self) -> dict[str, str]:
        return {
            "error_code": self.code.value,
            "error_type": type(self).__name__,
            "error_message": self.message,
            "owner": self.owner,
            "recovery_action": self.recovery_action,
        }


class InputError(BlackboxError):
    code = ErrorCode.E001


class SchemaError(BlackboxError):
    code = ErrorCode.E002


class GateError(BlackboxError):
    code = ErrorCode.E003


class ModelError(BlackboxError):
    code = ErrorCode.E004


class SimulationError(BlackboxError):
    code = ErrorCode.E005


class FragilityError(BlackboxError):
    code = ErrorCode.E006


class CertificateError(BlackboxError):
    code = ErrorCode.E007


class ApiError(BlackboxError):
    code = ErrorCode.E008


class DependencyError(BlackboxError):
    code = ErrorCode.E010


class DataLeakError(BlackboxError):
    code = ErrorCode.E012
