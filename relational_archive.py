"""Verified ZIP/CSV and XLSX interchange for the COT relational archive.

R8 source JSON is canonical in this migration step. Relational rows are checked
projections; edits to mapped fields must use relational_model.edit_r8_field().
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import uuid4
import zlib
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell

import relational_model as model


ZIP_FORMAT = "COT_RELATIONAL_ZIP_CSV"
XLSX_FORMAT = "COT_RELATIONAL_XLSX"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_FILE_COUNT = 128
MAX_COMPRESSION_RATIO = 150
MAX_ROWS = 500_000
XLSX_CELL_LIMIT = 30_000
XLSX_CHUNK_CHARS = 4_000
XLSX_META_SHEET = "COT_MANIFEST"
XLSX_DICTIONARY_SHEET = "COT_DIZIONARIO"
XLSX_CHUNKS_SHEET = "COT_BLOCCHI"


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _table_csv(dataset: dict[str, Any], name: str) -> bytes:
    out = StringIO(newline="")
    writer = csv.writer(out, dialect="excel", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    spec = model.TABLES[name]
    writer.writerow(spec.columns)
    rows = dataset[name]
    if len(rows) > MAX_ROWS: raise ValueError(f"{name}: superato limite righe {MAX_ROWS}")
    for row in rows:
        writer.writerow([_encode(row.get(column)) for column in spec.columns])
    return out.getvalue().encode("utf-8")


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write_zip_member(zf: ZipFile, name: str, data: bytes) -> None:
    compressed_size = max(1, len(zlib.compress(data, level=6)))
    compression = ZIP_STORED if len(data) / compressed_size > MAX_COMPRESSION_RATIO else ZIP_DEFLATED
    zf.writestr(name, data, compress_type=compression, compresslevel=6 if compression == ZIP_DEFLATED else None)


def _manifest(dataset: dict[str, Any], archive_format: str) -> dict[str, Any]:
    tables = {name: {"sha256": _hash(_table_csv(dataset, name)), "rows": len(dataset[name])}
              for name in model.TABLES}
    unmapped = [row for row in dataset["r8_source_fields"] if row["mapped_to"].startswith("SOURCE_JSON")]
    return {
        **model.schema_manifest(),
        "format": archive_format,
        "archive_id": f"COT-{uuid4().hex.upper()}",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "serialization": {"encoding": "UTF-8", "record_terminator": "CRLF", "cell_value": "one JSON value per CSV cell; null and empty string remain distinct"},
        "files": ({f"tables/{name}.csv": value for name, value in tables.items()} if archive_format == ZIP_FORMAT else {}),
        "sheets": (tables if archive_format == XLSX_FORMAT else {}),
        "unmapped_field_count": len(unmapped),
        "unmapped_fields": [{"collection": r["source_collection"], "path": r["field_path"], "type": r["json_type"]} for r in unmapped],
        "r8_source_is_canonical": True,
        "relational_tables_are": "validated projections; write through edit_r8_field",
    }


def _validate_manifest_contract(manifest: dict[str, Any], archive_format: str) -> None:
    for key, expected in model.schema_manifest().items():
        if manifest.get(key) != expected:
            raise ValueError(f"Dizionario/schema del manifest alterato o incompatibile: {key}")
    if not isinstance(manifest.get("archive_id"), str) or not re.fullmatch(r"COT-[A-F0-9]{32}", manifest["archive_id"]):
        raise ValueError("Identificativo archivio non valido")
    try:
        datetime.fromisoformat(str(manifest.get("exported_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Data di esportazione manifest non ISO") from exc
    unmapped = manifest.get("unmapped_fields")
    if not isinstance(unmapped, list) or len(unmapped) != manifest.get("unmapped_field_count"):
        raise ValueError("Inventario campi non mappati incoerente")
    expected_entries = manifest.get("files", {}) if archive_format == ZIP_FORMAT else manifest.get("sheets", {})
    entry_keys = ({f"tables/{table}.csv" for table in model.TABLES} if archive_format == ZIP_FORMAT
                  else set(model.TABLES))
    if set(expected_entries) != entry_keys:
        raise ValueError("Hash/count tabella mancanti nel manifest")
    for entry, details in expected_entries.items():
        table = entry.removeprefix("tables/").removesuffix(".csv") if archive_format == ZIP_FORMAT else entry
        if (not isinstance(details, dict) or not isinstance(details.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", details["sha256"])
                or not isinstance(details.get("rows"), int) or details["rows"] < 0):
            raise ValueError(f"Hash/count tabella non valido nel manifest: {table}")


def validate_archive_dataset(dataset: dict[str, Any]) -> None:
    issues = model.validate_dataset(dataset) + model.validate_r8_projection(dataset)
    if issues: raise ValueError("Archivio non valido: " + "; ".join(issues[:12]))


def export_zip(dataset: dict[str, Any]) -> bytes:
    validate_archive_dataset(dataset)
    manifest = _manifest(dataset, ZIP_FORMAT)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    checksum = f"{_hash(manifest_bytes)}  manifest.json\n".encode("ascii")
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED, compresslevel=6, strict_timestamps=True) as zf:
        for name in model.TABLES:
            _write_zip_member(zf, f"tables/{name}.csv", _table_csv(dataset, name))
        _write_zip_member(zf, "manifest.json", manifest_bytes)
        _write_zip_member(zf, "manifest.sha256", checksum)
    if len(out.getvalue()) > MAX_ARCHIVE_BYTES:
        raise ValueError("Archivio ZIP oltre 100 MiB")
    return out.getvalue()


def _read_manifest(zf: ZipFile, names: set[str], fmt: str) -> dict[str, Any]:
    raw = zf.read("manifest.json")
    digest_line = zf.read("manifest.sha256").decode("ascii", errors="strict").strip().split()
    if len(digest_line) != 2 or digest_line[1] != "manifest.json" or digest_line[0] != _hash(raw):
        raise ValueError("Checksum del manifest non valido")
    try: manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ValueError("Manifest JSON non valido") from exc
    if manifest.get("schema_version") != model.SCHEMA_VERSION:
        raise ValueError(f"Versione schema non supportata: {manifest.get('schema_version')}")
    if manifest.get("format") != fmt: raise ValueError("Formato dichiarato nel manifest non corrispondente")
    _validate_manifest_contract(manifest, fmt)
    expected = {f"tables/{table}.csv" for table in model.TABLES}
    if set(manifest.get("files", {})) != expected: raise ValueError("Elenco file del manifest incompleto o incompatibile")
    if names != expected | {"manifest.json", "manifest.sha256"}:
        raise ValueError("Pacchetto incompleto o con file non dichiarati")
    return manifest


def _parse_csv(raw: bytes, table: str) -> list[dict[str, Any]]:
    try: stream = StringIO(raw.decode("utf-8", errors="strict"), newline="")
    except UnicodeDecodeError as exc: raise ValueError(f"{table}: CSV non UTF-8") from exc
    reader = csv.reader(stream, dialect="excel", strict=True)
    spec = model.TABLES[table]
    try: header = next(reader)
    except StopIteration as exc: raise ValueError(f"{table}: file CSV vuoto") from exc
    if tuple(header) != spec.columns: raise ValueError(f"{table}: intestazioni mancanti, extra o riordinate")
    rows = []
    try:
        for line, cells in enumerate(reader, 2):
            if len(cells) != len(spec.columns): raise ValueError(f"{table} riga {line}: colonne non corrispondenti")
            try: row = {col: json.loads(cell) for col, cell in zip(spec.columns, cells)}
            except json.JSONDecodeError as exc: raise ValueError(f"{table} riga {line}: cella JSON non valida") from exc
            rows.append(row)
            if len(rows) > MAX_ROWS: raise ValueError(f"{table}: superato limite righe {MAX_ROWS}")
    except csv.Error as exc: raise ValueError(f"{table}: CSV non valido: {exc}") from exc
    return rows


def import_zip(content: bytes) -> dict[str, Any]:
    if len(content) > MAX_ARCHIVE_BYTES: raise ValueError("Archivio ZIP oltre 100 MiB")
    try: zf = ZipFile(BytesIO(content), "r")
    except BadZipFile as exc: raise ValueError("Archivio ZIP danneggiato") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILE_COUNT: raise ValueError("Troppi file nell'archivio ZIP")
        names = [i.filename for i in infos]
        if len(names) != len(set(names)): raise ValueError("Nomi file duplicati nello ZIP")
        for info in infos:
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or info.is_dir():
                raise ValueError("Percorso ZIP non consentito")
            if info.file_size > MAX_UNCOMPRESSED_BYTES: raise ValueError("File ZIP oltre limite decompressione")
            if info.compress_size == 0 and info.file_size or info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError("Rapporto di compressione ZIP oltre il limite")
        total = sum(i.file_size for i in infos)
        if total > MAX_UNCOMPRESSED_BYTES: raise ValueError("Dimensione decompressa ZIP oltre 250 MiB")
        name_set = set(names)
        manifest = _read_manifest(zf, name_set, ZIP_FORMAT)
        dataset = model.empty_dataset()
        for table in model.TABLES:
            path = f"tables/{table}.csv"
            raw = zf.read(path)
            file_meta = manifest["files"][path]
            if _hash(raw) != file_meta.get("sha256"): raise ValueError(f"Checksum errato: {path}")
            rows = _parse_csv(raw, table)
            if len(rows) != file_meta.get("rows"): raise ValueError(f"Conteggio righe incoerente: {path}")
            dataset[table] = rows
        validate_archive_dataset(dataset)
        return dataset


def write_zip_atomic(path: str | Path, dataset: dict[str, Any]) -> None:
    """Write a complete archive then atomically replace the target file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = export_zip(dataset)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except Exception:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
        raise


def _cell_chunks(dataset: dict[str, Any]):
    records = []
    references = {}
    for table, spec in model.TABLES.items():
        for row_no, row in enumerate(dataset[table], 1):
            for column in spec.columns:
                encoded = _encode(row.get(column))
                if len(encoded) <= XLSX_CELL_LIMIT: continue
                ref = f"CELL:{table}:{row_no}:{column}"
                parts = [encoded[i:i + XLSX_CHUNK_CHARS] for i in range(0, len(encoded), XLSX_CHUNK_CHARS)]
                digest = _hash(encoded.encode("utf-8"))
                references[(table, row_no, column)] = {"$cot_xlsx_chunk_ref": ref}
                for part_no, part in enumerate(parts, 1):
                    records.append({"ref": ref, "chunk_no": part_no, "chunk_count": len(parts), "sha256": digest, "chunk_text": part})
    return references, records


def export_xlsx(dataset: dict[str, Any]) -> bytes:
    validate_archive_dataset(dataset)
    manifest = _manifest(dataset, XLSX_FORMAT)
    references, chunks = _cell_chunks(dataset)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    buffer = BytesIO()
    workbook = Workbook(write_only=True)

    def append_strings(sheet, values):
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=str(value))
            cell.data_type = "s"
            cells.append(cell)
        sheet.append(cells)

    for table, spec in model.TABLES.items():
        sheet = workbook.create_sheet(table[:31])
        append_strings(sheet, spec.columns)
        for row_no, row in enumerate(dataset[table], 1):
            values = [references.get((table, row_no, col), row.get(col)) for col in spec.columns]
            append_strings(sheet, [_encode(value) for value in values])
    meta_sheet = workbook.create_sheet(XLSX_META_SHEET)
    append_strings(meta_sheet, ("format", "sha256", "chunk_no", "chunk_count", "manifest_chunk"))
    manifest_hash = _hash(manifest_bytes.encode("utf-8"))
    manifest_chunks = [manifest_bytes[i:i + XLSX_CHUNK_CHARS] for i in range(0, len(manifest_bytes), XLSX_CHUNK_CHARS)]
    for i, part in enumerate(manifest_chunks, 1):
        append_strings(meta_sheet, (XLSX_FORMAT, manifest_hash, i, len(manifest_chunks), part))
    dic = workbook.create_sheet(XLSX_DICTIONARY_SHEET)
    dic_headers = ("table", "column", "primary_key", "required", "date", "foreign_keys")
    append_strings(dic, dic_headers)
    for name, spec in model.TABLES.items():
        for column in spec.columns:
            values = (name, column, column == spec.key, column in spec.required, column in spec.dates,
                      [parent for field, parent, _ in spec.refs if field == column])
            append_strings(dic, [_encode(value) for value in values])
    ch = workbook.create_sheet(XLSX_CHUNKS_SHEET)
    chunk_headers = ("ref", "chunk_no", "chunk_count", "sha256", "chunk_text")
    append_strings(ch, chunk_headers)
    for row in chunks: append_strings(ch, [_encode(row[key]) for key in chunk_headers])
    workbook.save(buffer)
    result = buffer.getvalue()
    if len(result) > MAX_ARCHIVE_BYTES: raise ValueError("XLSX oltre 100 MiB")
    return result


def _xlsx_value(value: Any, where: str):
    if value is None: raise ValueError(f"{where}: cella obbligatoria vuota; i null devono essere codificati come JSON null")
    if not isinstance(value, str): raise ValueError(f"{where}: cella non serializzata come testo JSON")
    try: return json.loads(value)
    except json.JSONDecodeError as exc: raise ValueError(f"{where}: cella JSON non valida") from exc


def import_xlsx(content: bytes) -> dict[str, Any]:
    if len(content) > MAX_ARCHIVE_BYTES: raise ValueError("XLSX oltre 100 MiB")
    try:
        with ZipFile(BytesIO(content), "r") as package:
            infos = package.infolist()
            if len(infos) > 2_000 or sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Dimensioni interne XLSX oltre i limiti")
            if any(Path(info.filename).is_absolute() or ".." in Path(info.filename).parts or "\\" in info.filename for info in infos):
                raise ValueError("Percorso interno XLSX non consentito")
            if any(info.compress_size == 0 and info.file_size or info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO for info in infos):
                raise ValueError("Rapporto di compressione XLSX oltre il limite")
    except BadZipFile as exc: raise ValueError("XLSX ZIP interno danneggiato") from exc
    try: wb = load_workbook(BytesIO(content), read_only=True, data_only=False)
    except Exception as exc: raise ValueError("File XLSX non valido") from exc
    required_sheets = {name[:31] for name in model.TABLES} | {XLSX_META_SHEET, XLSX_DICTIONARY_SHEET, XLSX_CHUNKS_SHEET}
    try:
        if set(wb.sheetnames) != required_sheets: raise ValueError("Fogli XLSX mancanti o non dichiarati")
        meta = wb[XLSX_META_SHEET]
        meta_rows = list(meta.iter_rows(min_row=1, values_only=True))
        if not meta_rows or meta_rows[0] != ("format", "sha256", "chunk_no", "chunk_count", "manifest_chunk"):
            raise ValueError("Foglio manifest XLSX non valido")
        manifest_parts = meta_rows[1:]
        if not manifest_parts or any(row[0] != XLSX_FORMAT for row in manifest_parts): raise ValueError("Manifest XLSX mancante o formato errato")
        manifest_hash = manifest_parts[0][1]
        count = int(manifest_parts[0][3])
        if len(manifest_parts) != count or [int(row[2]) for row in manifest_parts] != list(range(1, count + 1)) or any(row[1] != manifest_hash or int(row[3]) != count for row in manifest_parts):
            raise ValueError("Blocchi manifest XLSX incompleti")
        manifest_raw = "".join(row[4] for row in manifest_parts)
        if not isinstance(manifest_raw, str) or not isinstance(manifest_hash, str) or _hash(manifest_raw.encode("utf-8")) != manifest_hash:
            raise ValueError("Checksum manifest XLSX non valido")
        manifest = json.loads(manifest_raw)
        if manifest.get("format") != XLSX_FORMAT: raise ValueError("Formato XLSX nel manifest non corrispondente")
        if manifest.get("schema_version") != model.SCHEMA_VERSION: raise ValueError(f"Versione schema non supportata: {manifest.get('schema_version')}")
        _validate_manifest_contract(manifest, XLSX_FORMAT)
        dic = wb[XLSX_DICTIONARY_SHEET]
        dic_headers = ("table", "column", "primary_key", "required", "date", "foreign_keys")
        dic_rows = list(dic.iter_rows(values_only=True))
        if not dic_rows or tuple(dic_rows[0]) != dic_headers: raise ValueError("Dizionario campi XLSX non valido")
        expected_dictionary = []
        for name, spec in model.TABLES.items():
            for column in spec.columns:
                expected_dictionary.append((name, column, column == spec.key, column in spec.required, column in spec.dates,
                    [parent for field, parent, _ in spec.refs if field == column]))
        actual_dictionary = [tuple(_xlsx_value(cell, f"{XLSX_DICTIONARY_SHEET}!{r}") for cell in row)
                             for r, row in enumerate(dic_rows[1:], 2)]
        if actual_dictionary != expected_dictionary: raise ValueError("Dizionario campi alterato o incompatibile")
        dataset = model.empty_dataset()
        cell_chunks: dict[str, list[dict[str, Any]]] = {}
        chunk_sheet = wb[XLSX_CHUNKS_SHEET]
        chunk_headers = [cell.value for cell in next(chunk_sheet.iter_rows(min_row=1, max_row=1))]
        if chunk_headers != ["ref", "chunk_no", "chunk_count", "sha256", "chunk_text"]: raise ValueError("Intestazione foglio blocchi non valida")
        for row_no, cells in enumerate(chunk_sheet.iter_rows(min_row=2, values_only=True), 2):
            vals = [_xlsx_value(value, f"{XLSX_CHUNKS_SHEET}!{row_no}") for value in cells]
            if all(value is None for value in vals): continue
            item = dict(zip(chunk_headers, vals))
            cell_chunks.setdefault(str(item["ref"]), []).append(item)
        for table, spec in model.TABLES.items():
            sheet = wb[table[:31]]
            header = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
            if tuple(header) != spec.columns: raise ValueError(f"{table}: intestazioni XLSX non corrispondenti")
            parsed = []
            for row_no, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
                if all(value is None for value in cells): continue
                if len(cells) != len(spec.columns): raise ValueError(f"{table} riga {row_no}: colonne mancanti")
                row = {}
                for column, cell in zip(spec.columns, cells):
                    value = _xlsx_value(cell, f"{table}!{row_no}/{column}")
                    if isinstance(value, dict) and set(value) == {"$cot_xlsx_chunk_ref"}:
                        ref = value["$cot_xlsx_chunk_ref"]
                        parts = sorted(cell_chunks.get(ref, []), key=lambda part: int(part["chunk_no"]))
                        if not parts: raise ValueError(f"Blocco XLSX mancante: {ref}")
                        count = int(parts[0]["chunk_count"])
                        if [int(part["chunk_no"]) for part in parts] != list(range(1, count + 1)) or any(int(part["chunk_count"]) != count or part["sha256"] != parts[0]["sha256"] for part in parts):
                            raise ValueError(f"Sequenza blocchi XLSX non valida: {ref}")
                        encoded = "".join(part["chunk_text"] for part in parts)
                        if _hash(encoded.encode("utf-8")) != parts[0]["sha256"]: raise ValueError(f"Checksum blocchi XLSX errato: {ref}")
                        value = json.loads(encoded)
                        cell_chunks.pop(ref)
                    row[column] = value
                parsed.append(row)
                if len(parsed) > MAX_ROWS: raise ValueError(f"{table}: superato limite righe {MAX_ROWS}")
            dataset[table] = parsed
            if len(parsed) != manifest["sheets"][table]["rows"]:
                raise ValueError(f"Conteggio righe XLSX incoerente: {table}")
        if cell_chunks: raise ValueError("Blocchi XLSX senza cella proprietaria")
        for table in model.TABLES:
            logical = _hash(_table_csv(dataset, table))
            expected = manifest.get("sheets", {}).get(table, {}).get("sha256")
            if logical != expected: raise ValueError(f"Contenuto foglio alterato: {table}")
        validate_archive_dataset(dataset)
        return dataset
    finally:
        wb.close()
