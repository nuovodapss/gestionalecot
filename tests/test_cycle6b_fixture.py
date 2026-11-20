import unittest

from generate_cycle6b_fixture import make_cycle6b_payload
from relational_session import export_payload, import_archive


class Cycle6BFixtureTests(unittest.TestCase):
    def test_fixture_covers_requested_relationships_and_both_archive_formats(self):
        payload = make_cycle6b_payload()
        self.assertEqual(len(payload["patients"]), 20)
        patient_one_paths = [p for p in payload["dischargePathways"] if p["patientId"] == "TEST-PAT-0001"]
        self.assertGreaterEqual(sum(p["status"] == "OPEN" for p in patient_one_paths), 2)
        active = [c for c in payload["facilityContacts"] if c["pathwayId"] == "TEST-PATH-0001-A"]
        self.assertEqual(len(active), 3)
        self.assertEqual({c["facilityId"] for c in active}, {"TEST-FAC-01", "TEST-FAC-02", "TEST-FAC-03"})
        self.assertTrue(all(c["outcome"] == "In attesa" for c in active))
        self.assertTrue(payload["hospitalEpisodes"][0]["wardHistory"])
        self.assertTrue(payload["cotConsultations"])
        self.assertTrue(payload["events"])
        self.assertTrue(payload["revisions"])

        for fmt, suffix in (("ZIP/CSV", ".zip"), ("XLSX", ".xlsx")):
            with self.subTest(fmt=fmt):
                artifact = export_payload(payload, fmt, "cycle6b_fixture")
                loaded = import_archive(f"cycle6b_fixture{suffix}", artifact.content)
                self.assertEqual(loaded.payload, payload)
                self.assertEqual(loaded.dataset, artifact.dataset)


if __name__ == "__main__":
    unittest.main()
