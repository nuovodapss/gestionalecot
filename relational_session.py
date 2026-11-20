"""Volatile Streamlit session adapters for the relational R8 archive.

Nothing in this module writes to SQLite or another permanent store. A session
imports and validates a complete archive, edits the R8 payload in the browser,
then exports a newly verified ZIP/CSV or XLSX file for the operator to download.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import relational_archive as archive
import relational_model as model


@dataclass(frozen=True)
class LoadedArchive:
    filename: str
    dataset: dict[str, Any]
    payload: dict[str, Any]


@dataclass(frozen=True)
class ExportedArchive:
    filename: str
    mime_type: str
    content: bytes
    sha256: str
    dataset: dict[str, Any]
    payload: dict[str, Any]
    verified: bool


def import_archive(filename: str, content: bytes) -> LoadedArchive:
    """Import a complete ZIP/XLSX archive or fail before returning any state."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        dataset = archive.import_zip(content)
    elif suffix in (".xlsx", ".xlsm"):
        dataset = archive.import_xlsx(content)
    else:
        raise ValueError("Formato non supportato: selezionare un archivio .zip o .xlsx")
    payload = model.reconstruct_r8_payload(dataset)
    return LoadedArchive(filename=Path(filename).name, dataset=dataset, payload=payload)


def capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Capture an R8 V3.2 payload after UI edits and validate every projection."""
    dataset = model.capture_r8_source(payload)
    archive.validate_archive_dataset(dataset)
    return dataset


def export_payload(payload: dict[str, Any], output_format: str, stem: str = "COT_ARCHIVIO") -> ExportedArchive:
    """Export then re-import and compare the complete dataset and payload."""
    dataset = capture_payload(payload)
    if output_format == "ZIP/CSV":
        content = archive.export_zip(dataset)
        filename, mime = f"{stem}.zip", "application/zip"
        verified_dataset = archive.import_zip(content)
    elif output_format == "XLSX":
        content = archive.export_xlsx(dataset)
        filename = f"{stem}.xlsx"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        verified_dataset = archive.import_xlsx(content)
    else:
        raise ValueError("Formato di esportazione non supportato")
    verified_payload = model.reconstruct_r8_payload(verified_dataset)
    if verified_dataset != dataset or verified_payload != payload:
        raise ValueError("Verifica post-esportazione non superata: contenuto o payload divergente")
    from hashlib import sha256
    return ExportedArchive(filename, mime, content, sha256(content).hexdigest(), verified_dataset,
                           verified_payload, True)


def payload_bytes(payload: dict[str, Any]) -> int:
    """Return the UTF-8 size used to show the transfer estimate in the UI."""
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
