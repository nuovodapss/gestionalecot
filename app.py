"""Streamlit shell for the existing R8 UI and the relational file archive.

Run: ``.venv/bin/python -m streamlit run app.py``.
Session payloads exist only in Streamlit's volatile session state. No database
is used as the permanent source; the operator downloads a verified ZIP/XLSX.
Use synthetic data only until authentication, access control, and approved
deployment security are available.
"""
from __future__ import annotations

from pathlib import Path
import uuid

import streamlit as st
import streamlit.components.v1 as components

from relational_session import import_archive
from streamlit_bridge import process_bridge_event


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend'
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

st.set_page_config(
    page_title="COT · Gestionale integrato R8",
    layout='wide',
    initial_sidebar_state="collapsed",
)
st.markdown("""<style>
    [data-testid="stSidebar"] {display:none}
    [data-testid="stHeader"] {display:none}
    [data-testid="stAppViewContainer"] {background:white}
    .block-container {max-width:100%; padding:.5rem 1rem 0!important}
    [data-testid="stCustomComponentV1"] {border:0}
</style>""", unsafe_allow_html=True)


def _init_state() -> None:
    defaults = {
        "cot_payload_command": None,
        "cot_probe_ack": None,
        "cot_export_ack": None,
        "cot_load_ack": None,
        "cot_import_pending": False,
        "cot_last_bridge_event": None,
        "cot_loaded_name": None,
        "cot_session_open": False,
        "cot_dirty": False,
        "cot_archive": None,
        "cot_pending_import": None,
        "cot_status": "Nessun archivio relazionale caricato.",
        "cot_error": None,
        "cot_pending_export_format": "ZIP/CSV",
        "cot_exported": None,
        "cot_probe_id": None,
        "cot_download_requested": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _process_bridge_event(event: object) -> bool:
    return process_bridge_event(st.session_state, event)


_init_state()


def _mark_download_requested() -> None:
    st.session_state.cot_download_requested = True


component = components.declare_component('cot_r8_full_parity', path=str(FRONTEND))

st.markdown("""<div style="border:1px solid #dce7df;border-radius:10px;padding:9px 12px;
background:#f6fcf8;color:#355b42;font:12px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<strong>Archivio relazionale locale · ZIP/CSV consigliato · XLSX completo</strong><br>
La sessione è temporanea. Le modifiche non esportate possono andare perse con refresh o interruzione.
Il download offerto dal browser non conferma che il file sia stato conservato sul computer.
ZIP/XLSX non sono cifrati. Usare solo dati sintetici finché non è approvato un ambiente protetto.
</div>""", unsafe_allow_html=True)

with st.container(border=True):
    upload, import_action, bridge_action, format_action, export_action = st.columns([3, 1, 1, 1, 1])
    with upload:
        uploaded = st.file_uploader("Carica archivio relazionale", type=["zip", "xlsx"],
            key="cot_relational_upload", help="ZIP/CSV canonico oppure workbook XLSX completo")
    with import_action:
        st.write("")
        import_clicked = st.button("Valida e apri", type="primary",
            disabled=uploaded is None or st.session_state.cot_import_pending,
            key="cot_import_archive")
    with bridge_action:
        st.write("")
        probe_clicked = st.button("Verifica bridge", key="cot_bridge_probe",
            disabled=st.session_state.cot_import_pending)
    with format_action:
        selected_format = st.selectbox("Esportazione", ["ZIP/CSV", "XLSX"], key="cot_export_format")
    with export_action:
        st.write("")
        export_clicked = st.button("Prepara export", key="cot_prepare_export",
            disabled=not st.session_state.cot_session_open)

if import_clicked and uploaded is not None:
    try:
        if st.session_state.cot_session_open and st.session_state.cot_dirty:
            raise ValueError("Esporta o chiudi la sessione R8 corrente prima di sostituirla")
        content = uploaded.getvalue()
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("Archivio oltre il limite applicativo di 100 MiB")
        loaded = import_archive(uploaded.name, content)
        command_id = uuid.uuid4().hex
        st.session_state.cot_pending_import = {"command_id": command_id, "filename": loaded.filename,
            "dataset": loaded.dataset}
        st.session_state.cot_payload_command = {"id": command_id, "kind": "load_payload",
            "payload": loaded.payload, "filename": loaded.filename}
        st.session_state.cot_import_pending = True
        st.session_state.cot_load_ack = None
        st.session_state.cot_error = None
        st.session_state.cot_status = f"{loaded.filename}: validazione completata; apertura nell’R8 in corso."
    except Exception as exc:
        st.session_state.cot_error = f"Importazione bloccata; nessun caricamento parziale: {exc}"
        st.session_state.cot_status = "Archivio non caricato."

if probe_clicked:
    st.session_state.cot_probe_id = uuid.uuid4().hex
    st.session_state.cot_probe_ack = None
    st.session_state.cot_payload_command = {"id": uuid.uuid4().hex, "kind": "probe",
        "request_id": st.session_state.cot_probe_id}

if export_clicked:
    st.session_state.cot_pending_export_format = selected_format
    st.session_state.cot_exported = None
    st.session_state.cot_download_requested = False
    st.session_state.cot_export_ack = None
    st.session_state.cot_payload_command = {"id": uuid.uuid4().hex, "kind": "export_payload",
        "request_id": uuid.uuid4().hex, "format": selected_format}
    st.session_state.cot_status = "In attesa dello snapshot R8 per esportare e verificare il file…"

if st.session_state.cot_error:
    st.error(st.session_state.cot_error)
elif st.session_state.cot_probe_id and st.session_state.cot_probe_ack and st.session_state.cot_probe_ack.get("request_id") == st.session_state.cot_probe_id:
    if st.session_state.cot_probe_ack.get("confirmed"):
        st.success("Bridge bidirezionale verificato: JavaScript → Python → conferma Python → JavaScript → Python.")
    elif st.session_state.cot_probe_ack.get("ok"):
        st.info("Messaggio JavaScript ricevuto da Python; attendo conferma di ritorno dal frame.")
elif st.session_state.cot_exported:
    st.success(st.session_state.cot_status)
else:
    if st.session_state.cot_dirty:
        st.warning("Modifiche non esportate: prepara e scarica un nuovo archivio prima di chiudere o aggiornare.")
    else:
        st.info(st.session_state.cot_status)

if st.session_state.cot_exported and not st.session_state.cot_error:
    item = st.session_state.cot_exported
    st.download_button("Scarica archivio verificato", data=item.content, file_name=item.filename,
        mime=item.mime_type, key=f"cot_download_{item.sha256}", on_click=_mark_download_requested)
    download_state = "Download richiesto; la conservazione sul computer non è verificabile." if st.session_state.cot_download_requested else "Download non ancora richiesto."
    st.caption(f"Export preparato e reimportato · SHA-256 `{item.sha256}` · {download_state}")

if st.session_state.cot_import_pending:
    st.info("Apertura del file non cifrato in corso; i dati non sono ancora considerati caricati nell’R8.")
elif st.session_state.cot_session_open and st.session_state.cot_loaded_name:
    st.caption(f"Modalità: Archivio relazionale non cifrato · {st.session_state.cot_loaded_name}")

if st.session_state.cot_payload_command and st.session_state.cot_payload_command.get("kind") in ("load_payload", "export_payload"):
    st.caption("I contenuti dell’archivio passano dal browser a questa sessione Streamlit per validazione ed esportazione; non vengono scritti su SQLite.")

command = st.session_state.cot_payload_command or {}
ack = (st.session_state.cot_probe_ack if command.get("kind") == "probe"
       else st.session_state.cot_export_ack if command.get("kind") == "export_payload"
       else st.session_state.cot_load_ack if command.get("kind") == "loaded" else None)
result = component(
    command=st.session_state.cot_payload_command,
    ack=ack,
    key="cot_r8_full",
    default={"kind": "idle"},
)

if _process_bridge_event(result):
    st.rerun()
