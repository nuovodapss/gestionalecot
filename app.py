"""COT Streamlit - R8 interface parity pilot.

Run: streamlit run app.py
Use synthetic data only: NO live patient data, no authenticated user control.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from storage import InvalidEnvelope, SqliteEncryptedStore, StorageConflict

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend'

st.set_page_config(
    page_title='COT · Gestionale integrato R8',
    layout='wide',
    initial_sidebar_state='collapsed',
)

st.markdown('''<style>
    [data-testid="stSidebar"] {display:none}
    [data-testid="stHeader"] {display:none}
    [data-testid="stAppViewContainer"] {background:white}
    .block-container {max-width:100%; padding:0!important}
    [data-testid="stCustomComponentV1"] {border:0}
</style>''', unsafe_allow_html=True)

# Explicitly local demo storage. Do not deploy with real data on Community Cloud.
store_path = os.environ.get('COT_SQLITE_PATH', str(ROOT / 'data' / 'cot_r8_demo_encrypted.sqlite3'))
store = SqliteEncryptedStore(store_path)
component = components.declare_component('cot_r8_full_parity', path=str(FRONTEND))

if 'cot_ack' not in st.session_state:
    st.session_state.cot_ack = None
if 'cot_last_request' not in st.session_state:
    st.session_state.cot_last_request = None

current = store.latest()
ack = st.session_state.cot_ack
result = component(
    revision=current.revision,
    envelope=current.envelope,
    ack=ack,
    key='cot_r8_full',
    default={'kind':'idle'},
)

if isinstance(result, dict) and result.get('kind') == 'encrypted_snapshot':
    request_id = result.get('request_id')
    if isinstance(request_id, str) and request_id and request_id != st.session_state.cot_last_request:
        st.session_state.cot_last_request = request_id
        try:
            expected = int(result.get('expected_revision'))
            saved = store.put(result.get('envelope'), expected)
            st.session_state.cot_ack = {'ok': True, 'request_id': request_id, 'revision': saved.revision}
        except (StorageConflict, InvalidEnvelope, TypeError, ValueError) as exc:
            st.session_state.cot_ack = {'ok': False, 'request_id': request_id, 'error': str(exc)}
        st.rerun()
