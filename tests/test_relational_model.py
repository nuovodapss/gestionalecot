import unittest

from relational_model import (
    R8_COLLECTIONS, SCHEMA_VERSION, TABLES, capture_r8_source, empty_dataset,
    restore_source_record, schema_manifest, validate_dataset,
)


def small_payload():
    return {
        "version": 3, "meta": {"schema": "COT_ODC_FLOW_V3_2", "extra": "kept"},
        "config": {"facilities": [{"id": "0007", "name": "Fixture", "extension": {"a": 1}}], "futureDictionary": [{"key": "x"}]},
        **{name: [] for name in R8_COLLECTIONS},
        "patients": [{"id": "TEST-1", "surname": "FITTIZIO", "name": "UNO", "future": {"flag": True}, "longNote": "x" * 65_000}],
        "dischargePathways": [
            {"id": "PATH-1", "patientId": "TEST-1", "status": "OPEN"},
            {"id": "PATH-2", "patientId": "TEST-1", "status": "OPEN"},
        ],
    }


class RelationalModelTests(unittest.TestCase):
    def test_source_capture_keeps_full_payload_and_unknown_nested_fields(self):
        payload = small_payload()
        staged = capture_r8_source(payload)
        complete = next(row for row in staged["r8_source_records"] if row["source_collection"] == "__payload__")
        self.assertEqual(restore_source_record(staged, complete["source_record_key"]), payload)
        self.assertGreater(int(complete["json_chunk_count"]), 1)
        self.assertTrue(all(len(row["chunk_text"]) <= 30_000 for row in staged["r8_source_chunks"]))
        paths = {(row["source_collection"], row["field_path"]) for row in staged["r8_source_fields"]}
        self.assertIn(("patients", "future.flag"), paths)
        self.assertIn(("config", "futureDictionary[].key"), paths)
        self.assertEqual(len(staged["r8_source_fields"]), len({row["field_key"] for row in staged["r8_source_fields"]}))
        self.assertEqual(validate_dataset(staged), [])

    def test_source_checksum_detects_changed_chunk(self):
        staged = capture_r8_source(small_payload())
        staged["r8_source_chunks"][0]["chunk_text"] += "tamper"
        self.assertTrue(any("checksum non corrispondente" in issue for issue in validate_dataset(staged)))

    def test_model_manifest_contains_stable_text_ids_and_pathway_need_fk(self):
        manifest = schema_manifest()
        self.assertEqual(manifest["schema_version"], SCHEMA_VERSION)
        self.assertEqual(manifest["id_encoding"], "text")
        self.assertIn("episode_id", manifest["tables"]["hospital_episodes"]["columns"])
        refs = manifest["tables"]["facility_requests"]["foreign_keys"]
        self.assertIn({"column": "pathway_id", "references": "pathways", "nullable": False}, refs)
        self.assertEqual(len(TABLES), len(manifest["tables"]))

    def test_two_open_pathways_are_valid(self):
        data = empty_dataset()
        data["patients"] = [{"patient_id": "P-1", "surname": "TEST", "given_name": "UNO"}]
        data["pathways"] = [
            {"pathway_id": "PC-1", "patient_id": "P-1", "administrative_status": "OPEN"},
            {"pathway_id": "PC-2", "patient_id": "P-1", "administrative_status": "OPEN"},
        ]
        self.assertEqual(validate_dataset(data), [])

    def test_invalid_fk_and_duplicate_id_are_reported(self):
        data = empty_dataset()
        data["patients"] = [{"patient_id": "P-1", "surname": "TEST", "given_name": "UNO"}]
        data["pathways"] = [{"pathway_id": "PC-1", "patient_id": "MISSING"}, {"pathway_id": "PC-1", "patient_id": "P-1"}]
        issues = validate_dataset(data)
        self.assertTrue(any("ID duplicato PC-1" in issue for issue in issues))
        self.assertTrue(any("senza riferimento in patients" in issue for issue in issues))

    def test_dates_and_undeclared_columns_are_rejected(self):
        data = empty_dataset()
        data["patients"] = [{"patient_id": "P-1", "surname": "TEST", "given_name": "UNO"}]
        data["pathways"] = [{"pathway_id": "PC-1", "patient_id": "P-1", "opened_at": "31/12/26", "surprise": "x"}]
        issues = validate_dataset(data)
        self.assertTrue(any("data non ISO" in issue for issue in issues))
        self.assertTrue(any("colonne non dichiarate" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
