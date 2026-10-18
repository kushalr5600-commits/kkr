"""Curated open-dataset registry and optional OpenML adapter.

Registry entries are **metadata only** — no dataset bytes are bundled. Users
import via local upload or the documented OpenML adapter. Download attempts
are never fabricated: network failures surface as explicit errors.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.shared.errors import InputError

# Optional OpenML client — absent on many hosts including this AMD64 host.
try:  # pragma: no cover - availability varies
    import openml  # type: ignore

    OPENML_AVAILABLE = True
except Exception:  # noqa: BLE001
    openml = None  # type: ignore
    OPENML_AVAILABLE = False


@dataclass(frozen=True)
class RegistryEntry:
    registry_id: str
    title: str
    task: str  # fraud_detection | credit_risk | other
    target_semantics: str  # fraud | default | operational_failure | other
    source_url: str
    source_org: str
    version_id: str
    license: str
    license_status: str  # verified | declared_by_source | unknown
    attribution: str
    suggested_columns: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    openml_data_id: int | None = None
    download_status: str = "not_downloaded"  # not_downloaded | local_upload_required | downloaded


REGISTRY: dict[str, RegistryEntry] = {}


def _register(entry: RegistryEntry) -> None:
    REGISTRY[entry.registry_id] = entry


_register(
    RegistryEntry(
        registry_id="ulb_creditcard_fraud",
        title="ULB/Worldline Credit Card Fraud (Kaggle mirror metadata)",
        task="fraud_detection",
        target_semantics="fraud",
        source_url="https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud",
        source_org="ULB / Worldline",
        version_id="creditcard.csv (Kaggle dataset)",
        license="CC BY 4.0 (as stated on Kaggle page — re-verify before redistribution)",
        license_status="declared_by_source",
        attribution="Andrea Dal Pozzolo et al., Kaggle mlg-ulb/creditcardfraud",
        suggested_columns={
            "amount": "Amount",
            "label": "Class",
            "id": "Time",
            "account_id": "V1",
        },
        notes=(
            "PCA-transformed features V1–V28; Time/Amount are original scales. "
            "Not bundled — import by uploading a local copy after accepting the "
            "upstream terms. Class=1 is fraud."
        ),
    )
)

_register(
    RegistryEntry(
        registry_id="paysim_mobile_money",
        title="PaySim mobile money simulation dataset",
        task="fraud_detection",
        target_semantics="fraud",
        source_url="https://www.kaggle.com/datasets/ealaxi/paysim1",
        source_org="PaySim (research simulation)",
        version_id="PS_20174392719 1.csv (Kaggle)",
        license="CC BY-NC-SA 4.0 (as stated on Kaggle — verify before any redistribution)",
        license_status="declared_by_source",
        attribution="PaySim: agent-based mobile money simulator (Kaggle ealaxi/paysim1)",
        suggested_columns={
            "amount": "amount",
            "label": "isFraud",
            "id": "step",
            "account_id": "nameOrig",
        },
        notes=(
            "Synthetic mobile-money logs. isFraud is a simulation outcome, not a "
            "real bank loss label. Not bundled — local upload only."
        ),
        download_status="local_upload_required",
    )
)

_register(
    RegistryEntry(
        registry_id="uci_default_credit_card",
        title="UCI Default of Credit Card Clients",
        task="credit_risk",
        target_semantics="default",
        source_url="https://archive.ics.uci.edu/ml/datasets/default+of+credit+card+clients",
        source_org="UCI ML Repository / ICIAR",
        version_id="default of credit card clients dataset (Yeh & Liao)",
        license="CC BY 4.0 (UCI page)",
        license_status="declared_by_source",
        attribution="Yeh, I.-C. & Lien, C.-H., UCI ML Repository",
        suggested_columns={
            "amount": "PAY_AMT1",
            "label": "default.payment.next.month",
            "id": "ID",
            "account_id": "ID",
        },
        notes=(
            "Credit-risk default prediction — NOT a fraud or stress-failure label. "
            "Evaluate as credit_risk only; never equate with synthetic stress failures. "
            "Not bundled — download from UCI after reading the license."
        ),
        openml_data_id=None,
    )
)


def list_registry() -> list[dict[str, Any]]:
    out = []
    for entry in REGISTRY.values():
        item = asdict(entry)
        item["local_import_supported"] = True
        item["openml_client_available"] = OPENML_AVAILABLE
        out.append(item)
    return out


def get_entry(registry_id: str) -> RegistryEntry:
    if registry_id not in REGISTRY:
        raise InputError(f"unknown registry_id {registry_id!r}")
    return REGISTRY[registry_id]


def mark_local_upload(registry_id: str, sha256: str, row_count: int) -> RegistryEntry:
    entry = get_entry(registry_id)
    # Registry is a frozen-ish catalog; return an updated snapshot without mutating
    # module state for immutable dataclass — callers attach import results separately.
    return entry


def openml_import_status() -> dict[str, Any]:
    return {
        "openml_package_installed": OPENML_AVAILABLE,
        "network_download_enabled": False,
        "policy": "local upload only unless a human enables network download on an authorized host",
    }


def try_openml_fetch(data_id: int, cache_dir: Path | None = None) -> dict[str, Any]:
    """Attempt OpenML download only if the optional package is present.

    Never fabricates success. Network is not assumed.
    """
    if not OPENML_AVAILABLE:
        return {
            "status": "unavailable",
            "reason": "openml package not installed",
            "recovery_action": "upload a local copy via Dataset Studio",
        }
    try:  # pragma: no cover - network path
        dataset = openml.datasets.get_dataset(data_id)
        name = dataset.name
        return {
            "status": "metadata_ok",
            "openml_name": name,
            "data_id": data_id,
            "note": "full file download not auto-performed; use OpenML UI or local upload",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
            "recovery_action": "upload a local copy via Dataset Studio",
        }


def write_registry_snapshot(path: Path) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": list_registry(),
        "openml": openml_import_status(),
    }
    blob = json.dumps(payload, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()
