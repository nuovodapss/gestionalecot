import unittest

from relational_fixture import make_payload
import relational_model as model
from streamlit_bridge import process_bridge_event


def state(**overrides):
    result = {
        "cot_last_bridge_event": None,
        "cot_probe_id": "probe-1",
        "cot_probe_ack": None,
        "cot_payload_command": None,
        "cot_pending_import": None,
        "cot_import_pending": False,
        "cot_archive": {"old": "dataset"},
        "cot_loaded_name": "old.zip",
        "cot_session_open": False,
        "cot_dirty": False,
        "cot_exported": None,
        "cot_download_requested": False,
        "cot_load_ack": None,
        "cot_status": "old",
        "cot_error": None,
        "cot_pending_export_format": "ZIP/CSV",
        "cot_export_ack": None,
    }
    result.update(overrides)
    return result


class StreamlitBridgeStateTests(unittest.TestCase):
    def test_probe_requires_python_ack_and_javascript_confirmation(self):
        current = state()
        self.assertTrue(process_bridge_event(current, {
            "kind": "probe", "event_id": "p1", "request_id": "probe-1",
        }))
        self.assertFalse(current["cot_probe_ack"].get("confirmed", False))
        self.assertFalse(process_bridge_event(current, {
            "kind": "probe_ack", "event_id": "p2", "request_id": "wrong",
        }))
        self.assertTrue(process_bridge_event(current, {
            "kind": "probe_ack", "event_id": "p3", "request_id": "probe-1",
        }))
        self.assertTrue(current["cot_probe_ack"]["confirmed"])
        self.assertFalse(process_bridge_event(current, {
            "kind": "probe_ack", "event_id": "p3", "request_id": "probe-1",
        }))

    def test_session_snapshot_does_not_promote_import_to_open(self):
        current = state(
            cot_payload_command={"id": "load-1", "kind": "load_payload"},
            cot_pending_import={"command_id": "load-1", "filename": "new.zip", "dataset": {"new": True}},
            cot_import_pending=True,
        )
        self.assertTrue(process_bridge_event(current, {
            "kind": "session_state", "event_id": "s1", "open": True, "dirty": False,
        }))
        self.assertEqual(current["cot_payload_command"]["kind"], "load_payload")
        self.assertFalse(current["cot_session_open"])
        self.assertEqual(current["cot_loaded_name"], "old.zip")
        self.assertEqual(current["cot_archive"], {"old": "dataset"})

    def test_relational_archive_commits_only_after_matching_loaded_ack(self):
        dataset = model.capture_r8_source(make_payload())
        current = state(
            cot_payload_command={"id": "load-2", "kind": "load_payload"},
            cot_pending_import={"command_id": "load-2", "filename": "fixture.zip", "dataset": dataset},
            cot_import_pending=True,
        )
        self.assertFalse(process_bridge_event(current, {
            "kind": "loaded", "event_id": "l0", "request_id": "stale",
        }))
        self.assertFalse(current["cot_session_open"])
        self.assertTrue(process_bridge_event(current, {
            "kind": "loaded", "event_id": "l1", "request_id": "load-2",
        }))
        self.assertTrue(current["cot_session_open"])
        self.assertEqual(current["cot_loaded_name"], "fixture.zip")
        self.assertEqual(current["cot_archive"], dataset)
        self.assertFalse(current["cot_import_pending"])
        self.assertIsNone(current["cot_pending_import"])

    def test_failed_relational_open_keeps_previous_archive_state(self):
        current = state(
            cot_payload_command={"id": "load-3", "kind": "load_payload"},
            cot_pending_import={"command_id": "load-3", "filename": "bad.zip", "dataset": {"new": True}},
            cot_import_pending=True,
        )
        self.assertTrue(process_bridge_event(current, {
            "kind": "bridge_error", "event_id": "e1", "request_id": "load-3",
            "command_kind": "load_payload", "error": "schema non valido",
        }))
        self.assertFalse(current["cot_session_open"])
        self.assertEqual(current["cot_loaded_name"], "old.zip")
        self.assertEqual(current["cot_archive"], {"old": "dataset"})
        self.assertFalse(current["cot_import_pending"])
        self.assertIsNone(current["cot_pending_import"])

    def test_export_ignores_stale_payload_and_marks_matching_export_verified(self):
        payload = make_payload()
        current = state(cot_payload_command={"id": "export-4", "kind": "export_payload",
            "request_id": "request-4"})
        self.assertFalse(process_bridge_event(current, {
            "kind": "r8_payload", "event_id": "x0", "request_id": "stale", "payload": payload,
        }))
        self.assertTrue(process_bridge_event(current, {
            "kind": "r8_payload", "event_id": "x1", "request_id": "request-4", "payload": payload,
        }))
        self.assertTrue(current["cot_exported"].verified)
        self.assertEqual(current["cot_exported"].payload, payload)
        self.assertFalse(current["cot_download_requested"])


if __name__ == "__main__":
    unittest.main()
