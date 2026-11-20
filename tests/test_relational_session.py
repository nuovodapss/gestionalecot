from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relational_fixture import make_payload
import relational_archive as archive
import relational_session
import relational_model as model


class RelationalSessionTests(unittest.TestCase):
    def setUp(self):
        self.payload = make_payload()

    def test_uploaded_zip_and_xlsx_open_as_complete_r8_payloads(self):
        dataset = model.capture_r8_source(self.payload)
        for suffix, content in ((".zip", archive.export_zip(dataset)),
                                (".xlsx", archive.export_xlsx(dataset))):
            loaded = relational_session.import_archive("fixture" + suffix, content)
            self.assertEqual(loaded.payload, self.payload)
            self.assertEqual(loaded.dataset, dataset)

    def test_modified_r8_payload_exports_and_reimports_with_events_and_revisions(self):
        updated = model.reconstruct_r8_payload(model.capture_r8_source(self.payload))
        updated["patients"][0]["surname"] = "AGGIORNAMENTO DI COLLAUDO"
        updated["events"].append({"id":"TEST-EV-NEW","type":"LONGITUDINAL_UPDATE",
            "patientId":"TEST-PAT-0001","refType":"patient","refId":"TEST-PAT-0001",
            "at":"2026-11-18T14:00:00.000Z","recordedAt":"2026-11-18T14:01:00.000Z",
            "actor":"TEST","label":"Evento aggiunto dalla UI sintetica",
            "meta":{"marker":"Ω | #","nested":{"valid":True}}})
        updated["revisions"].append({"id":"TEST-REV-NEW","entityType":"patient",
            "entityId":"TEST-PAT-0001","effectiveAt":"2026-11-18",
            "recordedAt":"2026-11-18T14:01:00.000Z","actor":"TEST",
            "reason":"Aggiornamento sintetico di collaudo",
            "before":{"surname":"PAZIENTE TEST 01"},
            "after":{"surname":"AGGIORNAMENTO DI COLLAUDO"}})
        for output_format, suffix in (("ZIP/CSV", ".zip"), ("XLSX", ".xlsx")):
            result = relational_session.export_payload(updated, output_format, "COT_TEST")
            self.assertTrue(result.verified)
            self.assertEqual(Path(result.filename).suffix, suffix)
            restored = relational_session.import_archive(result.filename, result.content)
            self.assertEqual(restored.payload, updated)
            self.assertEqual(restored.dataset, result.dataset)
            self.assertIn("TEST-EV-NEW", {row["id"] for row in restored.payload["events"]})
            self.assertIn("TEST-REV-NEW", {row["id"] for row in restored.payload["revisions"]})

    def test_corrupt_or_unknown_upload_fails_without_partial_result(self):
        with self.assertRaisesRegex(ValueError, "danneggiato"):
            relational_session.import_archive("broken.zip", b"not a zip")
        with self.assertRaisesRegex(ValueError, "Formato non supportato"):
            relational_session.import_archive("encrypted.json", b"{}")

    def test_bad_payload_and_format_do_not_produce_export(self):
        broken = dict(self.payload)
        broken["meta"] = {"schema":"UNKNOWN"}
        with self.assertRaises(ValueError):
            relational_session.export_payload(broken, "ZIP/CSV")
        with self.assertRaisesRegex(ValueError, "Formato di esportazione"):
            relational_session.export_payload(self.payload, "PDF")


if __name__ == "__main__":
    unittest.main()
