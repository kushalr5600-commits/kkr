"""Dataset Studio storage: safe uploads, metadata, and removal.

Uploads land under ``backend/data/uploads/`` with generated ids (never client
filenames as paths). Only CSV and Parquet are accepted. Max size and row caps
come from config. Original bytes are hashed; previews never dump full rows to
logs.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np

from backend.shared import config
from backend.shared.errors import InputError

UPLOAD_ROOT = Path(__file__).resolve().parent / "uploads"
ALLOWED_SUFFIXES = {".csv", ".parquet"}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

logger = logging.getLogger("blackbox.datasets")

# Upper bound on parsed rows held in the in-memory cache per dataset. Capped at
# MAX_ROWS+1 so the "too many rows" rejection is reachable and row_count is
# truthful (never a silent truncation presented as the full dataset).
def _max_read_rows() -> int:
    return config.DATASET_MAX_ROWS + 1


# Bound the in-memory row cache so repeated uploads cannot exhaust RAM. Small
# LRU: only the most recently used datasets keep parsed rows; the rest reload
# from disk on demand.
_ROW_CACHE_MAX = 8


@dataclass
class DatasetMeta:
    dataset_id: str
    display_name: str
    source_filename: str
    format: Literal["csv", "parquet"]
    sha256: str
    byte_size: int
    row_count: int
    column_count: int
    columns: list[dict[str, Any]]
    missing: dict[str, int]
    duplicate_rows: int
    numeric_summary: dict[str, dict[str, float]] = field(default_factory=dict)
    mapping: dict[str, str] | None = None
    label_semantics: str | None = None
    attribution: str = ""
    license: str = ""
    license_status: str = "unknown"
    source_url: str = ""
    imported_at: str = ""
    registry_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "display_name": self.display_name,
            "source_filename": self.source_filename,
            "format": self.format,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "missing": self.missing,
            "duplicate_rows": self.duplicate_rows,
            "numeric_summary": self.numeric_summary,
            "mapping": self.mapping,
            "label_semantics": self.label_semantics,
            "attribution": self.attribution,
            "license": self.license,
            "license_status": self.license_status,
            "source_url": self.source_url,
            "imported_at": self.imported_at,
            "registry_id": self.registry_id,
        }


def _safe_stem(filename: str) -> str:
    stem = Path(filename).name
    stem = _SAFE_NAME.sub("_", stem).strip("._") or "dataset"
    return stem[:80]


def _read_csv_bytes(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise InputError("CSV has no header row")
    cap = _max_read_rows()
    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(reader):
        if i >= cap:
            break
        rows.append({(k or "").strip(): ("" if v is None else str(v).strip()) for k, v in raw.items()})
    return rows


def _read_parquet_bytes(data: bytes) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except Exception as exc:  # noqa: BLE001
        raise InputError(
            "Parquet import requires pandas",
            recovery_action="install optional package or upload CSV",
        ) from exc
    try:
        df = pd.read_parquet(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise InputError(f"unreadable Parquet file: {type(exc).__name__}") from exc
    df = df.head(_max_read_rows())
    # Convert to plain JSON-safe dicts; no arbitrary object pickles.
    records = df.to_dict(orient="records")
    out: list[dict[str, Any]] = []
    for rec in records:
        row = {}
        for k, v in rec.items():
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                row[str(k)] = ""
            elif hasattr(v, "item"):
                try:
                    row[str(k)] = str(v.item())
                except Exception:  # noqa: BLE001
                    row[str(k)] = str(v)
            else:
                row[str(k)] = str(v)
        out.append(row)
    return out


def _infer_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    keys = list(rows[0].keys())
    cols: list[dict[str, Any]] = []
    for key in keys:
        values = [r.get(key, "") for r in rows]
        non_empty = [v for v in values if v != ""]
        missing = len(values) - len(non_empty)
        numeric = 0
        for v in non_empty[:200]:
            try:
                float(v)
                numeric += 1
            except ValueError:
                pass
        sample_n = min(len(non_empty), 200)
        inferred = "number" if sample_n and numeric / sample_n > 0.9 else "string"
        if key.lower() in {"timestamp", "time", "datetime", "date"} and inferred == "string":
            inferred = "datetime_string"
        cols.append(
            {
                "name": key,
                "inferred_type": inferred,
                "non_null": len(non_empty),
                "missing": missing,
                "unique_sample": sorted({v for v in non_empty[:50]})[:5],
            }
        )
    return cols


def _numeric_summary(rows: list[dict[str, Any]], columns: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for col in columns:
        if col["inferred_type"] != "number":
            continue
        vals = []
        for r in rows:
            raw = r.get(col["name"], "")
            if raw == "":
                continue
            try:
                vals.append(float(raw))
            except ValueError:
                continue
        if not vals:
            continue
        arr = np.asarray(vals, dtype=float)
        summary[col["name"]] = {
            "min": float(arr.min()),
            "max": float(arr.max()),
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=0)),
            "p50": float(np.percentile(arr, 50)),
        }
    return summary


class DatasetStore:
    """In-memory index + on-disk bytes for uploaded datasets."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else UPLOAD_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.root / "index.json"
        self._index: dict[str, DatasetMeta] = {}
        # Bounded LRU of parsed rows; key order = least- to most-recently used.
        self._rows: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._load_index()

    def _load_index(self) -> None:
        if self._meta_path.exists():
            try:
                payload = json.loads(self._meta_path.read_text(encoding="utf-8"))
                for item in payload.get("datasets", []):
                    meta = DatasetMeta(**item)
                    self._index[meta.dataset_id] = meta
            except (OSError, ValueError, TypeError) as exc:
                # Loud, not silent: a corrupt index orphans stored payloads. Keep
                # the reset (unrecoverable) but make it observable.
                logger.error(
                    "dataset index.json is unreadable (%s: %s); starting with an empty "
                    "index. Stored payload files under %s are orphaned.",
                    type(exc).__name__, exc, self.root,
                )
                self._index = {}

    def _save_index(self) -> None:
        payload = {"datasets": [m.to_dict() for m in self._index.values()]}
        # Atomic write: truncate-to-temp then rename, so concurrent readers never
        # see a torn/half-written index.
        tmp_path = self._meta_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._meta_path)

    def _cache_put(self, dataset_id: str, rows: list[dict[str, Any]]) -> None:
        self._rows[dataset_id] = rows
        self._rows.move_to_end(dataset_id)
        while len(self._rows) > _ROW_CACHE_MAX:
            self._rows.popitem(last=False)  # evict least-recently used

    def list(self) -> list[dict[str, Any]]:
        return [m.to_dict() for m in sorted(self._index.values(), key=lambda m: m.imported_at, reverse=True)]

    def get(self, dataset_id: str) -> DatasetMeta:
        if dataset_id not in self._index:
            raise InputError(f"unknown dataset_id {dataset_id!r}")
        return self._index[dataset_id]

    def rows(self, dataset_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        self.get(dataset_id)
        with self._lock:
            cached = self._rows.get(dataset_id)
            if cached is not None:
                self._rows.move_to_end(dataset_id)
                rows = cached
            else:
                path = self._data_path(dataset_id)
                if not path.exists():
                    raise InputError(f"dataset payload missing for {dataset_id!r}")
                fmt = self._index[dataset_id].format
                data = path.read_bytes()
                rows = _read_csv_bytes(data) if fmt == "csv" else _read_parquet_bytes(data)
                self._cache_put(dataset_id, rows)
        return rows if limit is None else rows[:limit]

    def _data_path(self, dataset_id: str) -> Path:
        meta = self._index[dataset_id]
        return self.root / f"{dataset_id}.{meta.format}"

    def ingest_bytes(
        self,
        filename: str,
        data: bytes,
        display_name: str | None = None,
        attribution: str = "",
        license_name: str = "",
        source_url: str = "",
        registry_id: str | None = None,
        label_semantics: str | None = None,
    ) -> DatasetMeta:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise InputError(
                f"unsupported file type {suffix!r}; allowed: csv, parquet",
                recovery_action="convert to CSV and re-upload",
            )
        if len(data) > config.DATASET_MAX_BYTES:
            raise InputError(
                f"file exceeds max size ({len(data)} > {config.DATASET_MAX_BYTES} bytes)",
                recovery_action="upload a smaller sample or subset the dataset offline",
            )
        if len(data) == 0:
            raise InputError("uploaded file is empty")

        fmt: Literal["csv", "parquet"] = "csv" if suffix == ".csv" else "parquet"
        rows = _read_csv_bytes(data) if fmt == "csv" else _read_parquet_bytes(data)
        if not rows:
            raise InputError("dataset has a header but no data rows")
        if len(rows) > config.DATASET_MAX_ROWS:
            raise InputError(
                f"dataset has too many rows ({len(rows)} > {config.DATASET_MAX_ROWS})",
                recovery_action="sample offline and re-upload",
            )

        columns = _infer_columns(rows)
        missing = {c["name"]: c["missing"] for c in columns if c["missing"]}
        # Duplicate detection on stringified rows (capped).
        seen: set[str] = set()
        duplicates = 0
        for r in rows[:5000]:
            key = json.dumps([r.get(c["name"], "") for c in columns], sort_keys=False)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)

        dataset_id = "DS-" + uuid.uuid4().hex[:10]
        safe_stem = _safe_stem(filename)
        payload_path = self.root / f"{dataset_id}.{fmt}"
        payload_path.write_bytes(data)
        meta = DatasetMeta(
            dataset_id=dataset_id,
            display_name=(display_name or safe_stem)[:120],
            source_filename=safe_stem,
            format=fmt,
            sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            row_count=len(rows),
            column_count=len(columns),
            columns=columns,
            missing=missing,
            duplicate_rows=duplicates,
            numeric_summary=_numeric_summary(rows, columns),
            attribution=attribution,
            license=license_name,
            license_status="declared" if license_name else "unknown",
            source_url=source_url,
            imported_at=datetime.now(timezone.utc).isoformat(),
            registry_id=registry_id,
            label_semantics=label_semantics,
        )
        with self._lock:
            self._index[dataset_id] = meta
            self._cache_put(dataset_id, rows)
            self._save_index()
        return meta

    def set_mapping(self, dataset_id: str, mapping: dict[str, str], label_semantics: str | None = None) -> DatasetMeta:
        meta = self.get(dataset_id)
        required = ("id", "account_id", "amount", "timestamp", "transaction_type")
        missing_keys = [k for k in required if not mapping.get(k)]
        if missing_keys:
            raise InputError(
                f"mapping missing required fields: {', '.join(missing_keys)}",
                recovery_action="map id, account_id, amount, timestamp, transaction_type",
            )
        cols = {c["name"] for c in meta.columns}
        unknown = [v for k, v in mapping.items() if v and v not in cols]
        if unknown:
            raise InputError(f"mapping references unknown columns: {', '.join(unknown)}")
        if label_semantics not in {None, "fraud", "default", "operational_failure", "other"}:
            raise InputError("label_semantics must be fraud|default|operational_failure|other")
        if mapping.get("label") and not label_semantics:
            raise InputError("label_semantics is required when a label column is mapped")
        with self._lock:
            meta.mapping = dict(mapping)
            meta.label_semantics = label_semantics
            self._save_index()
        return meta

    def remove(self, dataset_id: str) -> None:
        meta = self.get(dataset_id)
        path = self._data_path(dataset_id)
        if path.exists():
            path.unlink()
        with self._lock:
            self._index.pop(dataset_id, None)
            self._rows.pop(dataset_id, None)
            self._save_index()


# Module-level store used by the API (path-safe under backend/data/uploads).
default_store = DatasetStore()
