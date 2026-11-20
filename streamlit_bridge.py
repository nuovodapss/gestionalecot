"""Small, idempotent state reducer for events returned by the R8 component."""
from datetime import datetime
from typing import Any, MutableMapping

from relational_session import export_payload


def process_bridge_event(state: MutableMapping[str, Any], event: object) -> bool:
    if not isinstance(event, dict):
        return False
    event_id = event.get("event_id")
    kind = event.get("kind")
    if not isinstance(event_id, str) or not event_id or event_id == state.get("cot_last_bridge_event"):
        return False

    if kind == "probe":
        request_id = event.get("request_id")
        if request_id != state.get("cot_probe_id"):
            return False
        state["cot_last_bridge_event"] = event_id
        state["cot_probe_ack"] = {"request_id": request_id, "kind": "probe", "ok": True}
        return True

    if kind == "probe_ack":
        request_id = event.get("request_id")
        ack = state.get("cot_probe_ack") or {}
        if request_id != state.get("cot_probe_id") or ack.get("request_id") != request_id or not ack.get("ok"):
            return False
        state["cot_last_bridge_event"] = event_id
        state["cot_probe_ack"] = {"request_id": request_id, "kind": "probe", "ok": True, "confirmed": True}
        return True

    if kind == "loaded":
        command = state.get("cot_payload_command") or {}
        pending = state.get("cot_pending_import") or {}
        request_id = event.get("request_id")
        if (command.get("kind") != "load_payload" or request_id != command.get("id")
                or pending.get("command_id") != request_id):
            return False
        state["cot_last_bridge_event"] = event_id
        state["cot_archive"] = pending["dataset"]
        state["cot_loaded_name"] = pending["filename"]
        state["cot_pending_import"] = None
        state["cot_payload_command"] = {"id": request_id, "kind": "loaded"}
        state["cot_session_open"] = True
        state["cot_import_pending"] = False
        state["cot_load_ack"] = {"request_id": request_id, "ok": True, "loaded": True}
        state["cot_dirty"] = False
        state["cot_exported"] = None
        state["cot_download_requested"] = False
        state["cot_error"] = None
        state["cot_status"] = f"{state['cot_loaded_name']}: archivio relazionale non cifrato validato e aperto."
        return True

    if kind == "session_state":
        state["cot_last_bridge_event"] = event_id
        if not state["cot_import_pending"]:
            state["cot_session_open"] = bool(event.get("open"))
        if event.get("dirty"):
            state["cot_dirty"] = True
            state["cot_exported"] = None
            state["cot_download_requested"] = False
        if state["cot_session_open"]:
            state["cot_status"] = "Sessione R8 aperta in memoria. Esportare prima di chiudere o aggiornare la pagina."
        elif state["cot_dirty"]:
            state["cot_status"] = "Sessione R8 chiusa prima dell’esportazione; le ultime modifiche in memoria non sono recuperabili."
        return True

    if kind == "r8_payload":
        command = state.get("cot_payload_command") or {}
        if command.get("kind") != "export_payload" or event.get("request_id") != command.get("request_id"):
            return False
        state["cot_last_bridge_event"] = event_id
        try:
            exported = export_payload(event.get("payload"), state["cot_pending_export_format"],
                f"COT_ARCHIVIO_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            state["cot_archive"] = exported.dataset
            state["cot_loaded_name"] = exported.filename
            state["cot_dirty"] = False
            state["cot_download_requested"] = False
            state["cot_exported"] = exported
            state["cot_status"] = "Export preparato, reimportato e verificato; il download non è ancora richiesto."
            state["cot_export_ack"] = {"request_id": event.get("request_id"), "ok": True,
                "sha256": exported.sha256, "filename": exported.filename}
            state["cot_error"] = None
        except Exception as exc:
            state["cot_exported"] = None
            state["cot_error"] = f"Esportazione/verifica non riuscita: {exc}"
            state["cot_export_ack"] = {"request_id": event.get("request_id"), "ok": False,
                "error": str(exc)}
        return True

    if kind == "bridge_error":
        command_kind = event.get("command_kind")
        command = state.get("cot_payload_command") or {}
        request_id = event.get("request_id")
        if command_kind == "load_payload":
            pending = state.get("cot_pending_import") or {}
            if command.get("kind") != "load_payload" or pending.get("command_id") != request_id:
                return False
            state["cot_import_pending"] = False
            state["cot_pending_import"] = None
            state["cot_payload_command"] = None
            state["cot_status"] = "Apertura R8 non completata; l’eventuale archivio precedente resta invariato."
        elif command_kind == "probe":
            if request_id != state.get("cot_probe_id"):
                return False
            state["cot_probe_ack"] = {"request_id": request_id, "kind": "probe", "ok": False}
        elif command_kind == "export_payload":
            if command.get("kind") != "export_payload" or request_id != command.get("request_id"):
                return False
            state["cot_exported"] = None
            state["cot_status"] = "Export non preparato; nessun file è stato verificato."
        state["cot_last_bridge_event"] = event_id
        state["cot_error"] = str(event.get("error") or "Errore nel bridge R8")
        return True

    return False
