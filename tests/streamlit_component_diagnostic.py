"""Run with `.venv/bin/python -m streamlit run tests/streamlit_component_diagnostic.py`.

This minimal v1 component isolates registration, rendering, height, and the
JavaScript → Python → JavaScript → Python handshake from the R8 document.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="Diagnostica componente Streamlit v1")
diagnostic = components.declare_component(
    "cot_v1_diagnostic",
    path=str(Path(__file__).resolve().parent / "component_v1_diagnostic"),
)
st.title("Diagnostica componente Streamlit v1")
ack = st.session_state.get("diagnostic_ack")
result = diagnostic(ack=ack, key="cot_v1_diagnostic", default=None)
if isinstance(result, dict):
    request_id = result.get("request_id")
    if result.get("kind") == "probe" and request_id:
        st.session_state["diagnostic_ack"] = {"kind": "probe", "request_id": request_id, "ok": True}
        st.session_state["diagnostic_status"] = "Richiesta JavaScript ricevuta; conferma inviata al frame."
        st.rerun()
    if result.get("kind") == "probe_ack" and request_id == (ack or {}).get("request_id"):
        st.session_state["diagnostic_ack"] = {
            "kind": "probe_ack", "request_id": request_id, "confirmed": True,
        }
        st.session_state["diagnostic_status"] = "Handshake JavaScript ↔ Python confermato."
st.write(st.session_state.get("diagnostic_status", "In attesa della prova dal frame."))
