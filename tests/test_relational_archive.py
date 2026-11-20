import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relational_fixture import make_payload
import relational_archive as archive
import relational_model as model


def dataset():
    return model.capture_r8_source(make_payload())


def forge_zip(data):
    """Create an archive without exporter validation to exercise importer gates."""
    manifest = archive._manifest(data, archive.ZIP_FORMAT)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
        for table in model.TABLES:
            zf.writestr(f"tables/{table}.csv", archive._table_csv(data, table))
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("manifest.sha256", f"{archive._hash(manifest_bytes)}  manifest.json\n")
    return out.getvalue()


def rewrite_zip(content, omit=(), alter_manifest=None, alter_file=None, update_file_manifest=True):
    files = {}
    with ZipFile(BytesIO(content)) as source:
        files = {info.filename: source.read(info.filename) for info in source.infolist()}
    manifest = json.loads(files["manifest.json"])
    if alter_file:
        name, value = alter_file
        files[name] = value
        if update_file_manifest:
            manifest["files"][name] = {"sha256": archive._hash(value),
                                        "rows": max(0, value.count(b"\r\n") - 1)}
    if alter_manifest: alter_manifest(manifest)
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    files["manifest.sha256"] = f"{archive._hash(files['manifest.json'])}  manifest.json\n".encode("ascii")
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as target:
        for name, value in files.items():
            if name not in omit: target.writestr(name, value)
    return out.getvalue()


class RelationalArchiveTests(unittest.TestCase):
    def setUp(self): self.payload = make_payload()

    def test_zip_csv_full_semantic_round_trip(self):
        original = model.capture_r8_source(self.payload)
        packed = archive.export_zip(original)
        restored_dataset = archive.import_zip(packed)
        self.assertEqual(model.reconstruct_r8_payload(restored_dataset), self.payload)
        self.assertEqual(restored_dataset, original)
        self.assertEqual(len(restored_dataset["patients"]), 20)
        self.assertEqual(len(restored_dataset["pathways"]), 23)
        self.assertEqual(len(restored_dataset["facility_requests"]), 4)
        self.assertEqual({row["initial_status"] for row in restored_dataset["facility_requests"]},
                         {"AWAITING_RESPONSE", "NO_RESPONSE", "ACCEPTED", "REJECTED"})
        manifest = model.schema_manifest()
        self.assertEqual((manifest["table_count"], manifest["business_table_count"],
                          manifest["source_staging_table_count"]), (26, 23, 3))

    def test_xlsx_full_round_trip_preserves_typed_cells_and_long_cell_chunks(self):
        original = model.capture_r8_source(self.payload)
        packed = archive.export_xlsx(original)
        restored_dataset = archive.import_xlsx(packed)
        self.assertEqual(model.reconstruct_r8_payload(restored_dataset), self.payload)
        self.assertEqual(restored_dataset, original)
        from openpyxl import load_workbook
        workbook = load_workbook(BytesIO(packed), read_only=True, data_only=True)
        try:
            self.assertGreater(sum(1 for _ in workbook[archive.XLSX_CHUNKS_SHEET].iter_rows(min_row=2)), 0)
        finally: workbook.close()

    def test_typed_edit_writes_through_without_dropping_extensions(self):
        staged = model.capture_r8_source(self.payload)
        edited = model.edit_r8_field(staged, "patients", "TEST-PAT-0001", "surname", "COGNOME MODIFICATO Ω")
        rebuilt = model.reconstruct_r8_payload(edited)
        self.assertEqual(rebuilt["patients"][0]["surname"], "COGNOME MODIFICATO Ω")
        self.assertEqual(rebuilt["patients"][0]["extraField"], self.payload["patients"][0]["extraField"])
        self.assertEqual(rebuilt["futureRootField"], self.payload["futureRootField"])
        self.assertEqual(archive.import_zip(archive.export_zip(edited))["patients"][0]["surname"], "COGNOME MODIFICATO Ω")

    def test_fixture_passes_immutable_r8_v32_case_validator(self):
        source_path = Path(__file__).resolve().parents[1] / "frontend" / "R8_ORIGINALE_IMMUTATO.html"
        script = r'''const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(process.argv[1],'utf8'),payload=JSON.parse(fs.readFileSync(0,'utf8'));
const start=source.indexOf("const COT_V3_SCHEMA='COT_ODC_FLOW_V3_2'"),end=source.indexOf('function validateDb',start);
if(start<0||end<0)throw new Error('R8 validator not found');
const ctx={payload};vm.createContext(ctx);vm.runInContext(source.slice(start,end)+'\nglobalThis.validationError=cotV32RecordError(payload);',ctx);
process.stdout.write(ctx.validationError||'');'''
        result = subprocess.run(["node", "-e", script, str(source_path)], input=json.dumps(self.payload),
            text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, "")

    def test_divergent_direct_projection_edit_is_rejected(self):
        staged = model.capture_r8_source(self.payload)
        staged["patients"][0]["surname"] = "EDIT SENZA WRITE THROUGH"
        self.assertTrue(any("proiezione diversa" in issue for issue in model.validate_r8_projection(staged)))
        with self.assertRaisesRegex(ValueError, "Archivio non valido"):
            archive.export_zip(staged)

    def test_import_is_idempotent_and_does_not_mutate_source(self):
        source = archive.export_zip(model.capture_r8_source(self.payload))
        before = bytes(source)
        one = archive.import_zip(source)
        two = archive.import_zip(source)
        self.assertEqual(one, two)
        self.assertEqual(source, before)

    def test_missing_csv_manifest_edit_and_checksum_error_are_blocked(self):
        valid = archive.export_zip(model.capture_r8_source(self.payload))
        with self.assertRaisesRegex(ValueError, "incompleto"):
            archive.import_zip(rewrite_zip(valid, omit=("tables/patients.csv",)))
        with ZipFile(BytesIO(valid)) as source:
            files = {i.filename: source.read(i.filename) for i in source.infolist()}
        files["manifest.json"] += b" "
        out = BytesIO()
        with ZipFile(out, "w") as target:
            for name, value in files.items(): target.writestr(name, value)
        with self.assertRaisesRegex(ValueError, "Checksum del manifest"):
            archive.import_zip(out.getvalue())
        bad = rewrite_zip(valid, alter_file=("tables/patients.csv", b"tampered"), update_file_manifest=False)
        with self.assertRaisesRegex(ValueError, "Checksum errato"):
            archive.import_zip(bad)
        bad_dictionary = rewrite_zip(valid, alter_manifest=lambda m: m["tables"]["patients"].update(primary_key="tampered"))
        with self.assertRaisesRegex(ValueError, "Dizionario/schema del manifest"):
            archive.import_zip(bad_dictionary)

    def test_future_version_duplicate_id_foreign_key_and_date_are_blocked(self):
        valid = archive.export_zip(model.capture_r8_source(self.payload))
        with self.assertRaisesRegex(ValueError, "Versione schema non supportata"):
            archive.import_zip(rewrite_zip(valid, alter_manifest=lambda m: m.update(schema_version="COT_RELATIONAL_99_0")))
        duplicate = model.capture_r8_source(self.payload)
        duplicate["patients"][1]["patient_id"] = duplicate["patients"][0]["patient_id"]
        with self.assertRaisesRegex(ValueError, "ID duplicato"):
            archive.import_zip(forge_zip(duplicate))
        broken_fk = model.capture_r8_source(self.payload)
        broken_fk["pathways"][0]["patient_id"] = "PATIENTE_ASSENTE"
        with self.assertRaisesRegex(ValueError, "senza riferimento"):
            archive.import_zip(forge_zip(broken_fk))
        bad_date = model.capture_r8_source(self.payload)
        bad_date["patients"][0]["birth_date"] = "31/12/1950"
        with self.assertRaisesRegex(ValueError, "data non ISO"):
            archive.import_zip(forge_zip(bad_date))

    def test_write_interruption_keeps_previous_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "COT_ARCHIVIO_TEST.zip"
            path.write_bytes(b"previous-complete-archive")
            with patch.object(archive.os, "replace", side_effect=OSError("simulated interruption")):
                with self.assertRaisesRegex(OSError, "interruption"):
                    archive.write_zip_atomic(path, model.capture_r8_source(self.payload))
            self.assertEqual(path.read_bytes(), b"previous-complete-archive")
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_xlsx_sheet_checksum_and_missing_sheet_are_blocked(self):
        from openpyxl import load_workbook
        valid = archive.export_xlsx(model.capture_r8_source(self.payload))
        workbook = load_workbook(BytesIO(valid))
        workbook["patients"]["B2"] = '"COGNOME ALTERATO"'
        out = BytesIO(); workbook.save(out); workbook.close()
        with self.assertRaisesRegex(ValueError, "Contenuto foglio alterato"):
            archive.import_xlsx(out.getvalue())
        workbook = load_workbook(BytesIO(valid)); del workbook["patients"]
        out = BytesIO(); workbook.save(out); workbook.close()
        with self.assertRaisesRegex(ValueError, "Fogli XLSX mancanti"):
            archive.import_xlsx(out.getvalue())


if __name__ == "__main__": unittest.main()
