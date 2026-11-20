from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitEntrypointTests(unittest.TestCase):
    def test_app_renders_relational_upload_controls_and_registered_component(self):
        app = Path(__file__).resolve().parents[1] / "app.py"
        result = AppTest.from_file(str(app)).run(timeout=20)
        self.assertEqual(len(result.exception), 0)
        self.assertEqual(len(result.get("file_uploader")), 1)
        self.assertIn("Verifica bridge", [button.label for button in result.button])
        self.assertIn("Prepara export", [button.label for button in result.button])
        self.assertGreaterEqual(len(result.get("component_instance")), 1)


if __name__ == "__main__":
    unittest.main()
