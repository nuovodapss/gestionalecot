from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class MinimalComponentDiagnosticTests(unittest.TestCase):
    def test_minimal_v1_component_registers_and_renders_in_app_test(self):
        app = Path(__file__).resolve().parent / "streamlit_component_diagnostic.py"
        result = AppTest.from_file(str(app)).run(timeout=20)
        self.assertEqual(len(result.exception), 0)
        self.assertGreaterEqual(len(result.get("component_instance")), 1)
        self.assertIn("In attesa della prova dal frame.", [x.value for x in result.get("markdown") + result.get("text")])

    def test_frontend_implements_v1_ready_render_value_and_height_messages(self):
        html = (Path(__file__).resolve().parent / "component_v1_diagnostic" / "index.html").read_text()
        for message_type in (
            "streamlit:componentReady", "streamlit:render",
            "streamlit:setComponentValue", "streamlit:setFrameHeight",
        ):
            with self.subTest(message_type=message_type):
                self.assertIn(message_type, html)


if __name__ == "__main__":
    unittest.main()
