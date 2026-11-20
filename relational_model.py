"""Versioned file-exchange schema for the COT longitudinal model.

This module defines the XLSX/CSV contract. It does not replace the encrypted R8
archive or convert uncertain legacy semantics into verified clinical facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any


SCHEMA_VERSION = "COT_RELATIONAL_1_0"
SOURCE_STAGING_TABLES = ("r8_source_records", "r8_source_chunks", "r8_source_fields")
R8_COLLECTIONS = (
    "patients", "hospitalEpisodes", "cotConsultations", "dischargePathways",
    "odcWaitingList", "odcStays", "odcAssessments", "facilityContacts",
    "events", "audit", "revisions", "cotCases", "cotCaseLinks",
    "cotCaseReconciliation",
)


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    key: str
    required: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    refs: tuple[tuple[str, str, bool], ...] = ()  # field, table, nullable
    choices: tuple[tuple[str, tuple[str, ...]], ...] = ()


# Fields are deliberately strings in the interchange contract, including IDs,
# dates, codes, and numeric-looking identifiers. Source JSON preserves extras.
TABLES: dict[str, Table] = {
    "patients": Table(("patient_id", "tax_code", "surname", "given_name", "birth_date", "residence_city", "residence_province", "residence_region", "created_at", "source_record_id"), "patient_id", ("patient_id",), ("birth_date",)),
    "facilities": Table(("facility_id", "name", "kind", "city", "province", "region", "active", "source_record_id"), "facility_id", ("facility_id", "name")),
    "wards": Table(("ward_id", "label", "facility_id", "active", "source_record_id"), "ward_id", ("ward_id", "label"), refs=(("facility_id", "facilities", True),)),
    "settings": Table(("setting_id", "code", "label", "subtype", "source_record_id"), "setting_id", ("setting_id", "label")),
    "hospital_episodes": Table(("episode_id", "patient_id", "admitted_at", "origin_macro", "origin_site", "origin_ward_id", "origin_ward_legacy", "legacy_status", "source_record_id"), "episode_id", ("episode_id", "patient_id"), ("admitted_at",), (("patient_id", "patients", False), ("origin_ward_id", "wards", True))),
    "consultations": Table(("consultation_id", "patient_id", "episode_id", "pathway_id", "requested_at", "responded_at", "requester", "response_status", "appropriateness", "status", "source_record_id"), "consultation_id", ("consultation_id", "patient_id"), ("requested_at", "responded_at"), (("patient_id", "patients", False), ("episode_id", "hospital_episodes", True), ("pathway_id", "pathways", True))),
    "pathways": Table(("pathway_id", "patient_id", "episode_id", "target", "requested_setting_id", "opened_at", "administrative_status", "administratively_closed_at", "outcome_at", "closure_reason", "source_record_id"), "pathway_id", ("pathway_id", "patient_id"), ("opened_at", "administratively_closed_at", "outcome_at"), (("patient_id", "patients", False), ("episode_id", "hospital_episodes", True), ("requested_setting_id", "settings", True)), (("administrative_status", ("OPEN", "CLOSED", "CANCELLED", "UNVERIFIED")),)),
    "care_needs": Table(("need_id", "patient_id", "category", "setting_id", "status", "effective_from", "effective_to", "certainty", "evidence_source", "notes", "source_record_id"), "need_id", ("need_id", "patient_id", "status", "certainty"), ("effective_from", "effective_to"), (("patient_id", "patients", False), ("setting_id", "settings", True)), (("status", ("OPEN", "SUSPENDED", "FULFILLED", "CANCELLED", "TO_VERIFY")), ("certainty", ("DOCUMENTED", "RECONSTRUCTED", "UNCERTAIN", "TO_VERIFY")))),
    "pathway_needs": Table(("link_id", "pathway_id", "need_id", "effective_at", "recorded_at", "operator", "certainty", "source_record_id"), "link_id", ("link_id", "pathway_id", "need_id"), ("effective_at", "recorded_at"), (("pathway_id", "pathways", False), ("need_id", "care_needs", False))),
    "facility_requests": Table(("request_id", "pathway_id", "need_id", "facility_id", "facility_legacy", "channel", "sent_at", "initial_status", "response_at", "reason", "auto_closed_by_request_id", "certainty", "source_record_id"), "request_id", ("request_id", "pathway_id", "initial_status"), ("sent_at", "response_at"), (("pathway_id", "pathways", False), ("need_id", "care_needs", True), ("facility_id", "facilities", True), ("auto_closed_by_request_id", "facility_requests", True)), (("initial_status", ("SENT", "ATTENTIONED", "ASSIGNED", "AWAITING_RESPONSE", "NO_RESPONSE", "ACCEPTED", "REJECTED", "WITHDRAWN", "CLOSED_BY_OTHER_ACCEPTANCE", "ADMISSION_CONFIRMED", "TO_VERIFY")),)),
    "request_channels": Table(("request_channel_id", "request_id", "channel", "effective_at", "recorded_at", "source_record_id"), "request_channel_id", ("request_channel_id", "request_id", "channel"), ("effective_at", "recorded_at"), (("request_id", "facility_requests", False),)),
    "request_events": Table(("event_id", "request_id", "event_type", "effective_at", "recorded_at", "operator", "old_value_json", "new_value_json", "reason", "source", "certainty", "source_record_id"), "event_id", ("event_id", "request_id", "event_type", "effective_at"), ("effective_at", "recorded_at"), (("request_id", "facility_requests", False),)),
    "location_events": Table(("location_event_id", "patient_id", "episode_id", "facility_id", "facility_legacy", "ward_id", "ward_legacy", "effective_at", "effective_to", "recorded_at", "status", "source", "certainty", "notes", "source_record_id"), "location_event_id", ("location_event_id", "patient_id", "effective_at", "status", "certainty"), ("effective_at", "effective_to", "recorded_at"), (("patient_id", "patients", False), ("episode_id", "hospital_episodes", True), ("facility_id", "facilities", True), ("ward_id", "wards", True))),
    "clinical_events": Table(("event_id", "patient_id", "entity_type", "entity_id", "event_type", "effective_at", "recorded_at", "operator", "old_value_json", "new_value_json", "reason", "source", "certainty", "notes", "source_record_id"), "event_id", ("event_id", "event_type"), ("effective_at", "recorded_at"), (("patient_id", "patients", True),)),
    "odc_waitlist": Table(("waitlist_id", "patient_id", "pathway_id", "unit_id", "entered_at", "planned_admission_at", "status", "closed_at", "source_record_id"), "waitlist_id", ("waitlist_id", "patient_id", "pathway_id"), ("entered_at", "planned_admission_at", "closed_at"), (("patient_id", "patients", False), ("pathway_id", "pathways", False))),
    "odc_stays": Table(("stay_id", "patient_id", "pathway_id", "unit_id", "admitted_at", "planned_discharge_at", "discharged_at", "planned_destination", "final_destination", "source_record_id"), "stay_id", ("stay_id", "patient_id", "pathway_id"), ("admitted_at", "planned_discharge_at", "discharged_at"), (("patient_id", "patients", False), ("pathway_id", "pathways", False))),
    "odc_assessments": Table(("assessment_id", "patient_id", "stay_id", "scale", "phase", "assessed_at", "score", "assessor", "source_record_id", "payload_json"), "assessment_id", ("assessment_id", "patient_id", "scale"), ("assessed_at",), (("patient_id", "patients", False), ("stay_id", "odc_stays", True))),
    "audit_events": Table(("audit_id", "recorded_at", "operator", "action", "entity_type", "entity_id", "reason", "payload_json", "source_record_id"), "audit_id", ("audit_id", "action"), ("recorded_at",)),
    "revisions": Table(("revision_id", "entity_type", "entity_id", "effective_at", "recorded_at", "operator", "reason", "before_json", "after_json", "supersedes_id", "source_record_id"), "revision_id", ("revision_id", "entity_type", "entity_id"), ("effective_at", "recorded_at")),
    "cot_cases": Table(("case_id", "patient_id", "created_at", "created_by", "schema_version", "source_record_id"), "case_id", ("case_id", "patient_id"), ("created_at",), (("patient_id", "patients", False),)),
    "cot_case_links": Table(("case_link_id", "patient_id", "case_id", "entity_type", "entity_id", "relation", "operation", "effective_at", "recorded_at", "source", "reason", "supersedes_id", "schema_version", "source_record_id"), "case_link_id", ("case_link_id", "patient_id", "case_id", "entity_type", "entity_id", "relation", "operation", "recorded_at"), ("effective_at", "recorded_at"), (("patient_id", "patients", False), ("case_id", "cot_cases", False))),
    "cot_case_reconciliation": Table(("reconciliation_id", "patient_id", "entity_type", "entity_id", "decision", "case_id", "relation", "source", "reason", "recorded_at", "actor", "supersedes_id", "schema_version", "source_record_id"), "reconciliation_id", ("reconciliation_id", "patient_id", "entity_type", "entity_id", "decision", "recorded_at"), ("recorded_at",), (("patient_id", "patients", False), ("case_id", "cot_cases", True))),
    "configuration_records": Table(("config_record_id", "dictionary", "entry_id", "ordinal", "value_json", "source_record_id"), "config_record_id", ("config_record_id", "dictionary", "value_json")),
    "r8_source_records": Table(("source_record_key", "source_collection", "source_id", "ordinal", "json_chunk_count", "sha256"), "source_record_key", ("source_record_key", "source_collection", "json_chunk_count", "sha256")),
    "r8_source_chunks": Table(("chunk_id", "source_record_key", "chunk_no", "chunk_text"), "chunk_id", ("chunk_id", "source_record_key", "chunk_no", "chunk_text"), refs=(("source_record_key", "r8_source_records", False),)),
    "r8_source_fields": Table(("field_key", "source_collection", "field_path", "json_type", "mapped_to"), "field_key", ("field_key", "source_collection", "field_path", "json_type", "mapped_to")),
}

R8_TO_RELATIONAL = {
    "patients": ("patients",),
    "hospitalEpisodes": ("hospital_episodes", "location_events"),
    "cotConsultations": ("consultations",),
    "dischargePathways": ("pathways", "care_needs", "pathway_needs"),
    "odcWaitingList": ("odc_waitlist",),
    "odcStays": ("odc_stays",),
    "odcAssessments": ("odc_assessments",),
    "facilityContacts": ("facility_requests", "request_channels"),
    "events": ("clinical_events", "location_events", "request_events"),
    "audit": ("audit_events",),
    "revisions": ("revisions",),
    "cotCases": ("cot_cases",),
    "cotCaseLinks": ("cot_case_links",),
    "cotCaseReconciliation": ("cot_case_reconciliation",),
    "config": ("facilities", "wards", "settings", "configuration_records"),
}

# Semantic mappings for stable, commonly used R8 properties. Every property not
# listed here is still losslessly retained in r8_source_records/r8_source_chunks.
R8_FIELD_MAPS = {
    "patients": {"id":"patients.patient_id", "taxCode":"patients.tax_code", "cf":"patients.tax_code", "surname":"patients.surname", "name":"patients.given_name", "birthDate":"patients.birth_date", "residenceCity":"patients.residence_city", "residenceProvince":"patients.residence_province", "residenceRegion":"patients.residence_region", "createdAt":"patients.created_at"},
    "hospitalEpisodes": {"id":"hospital_episodes.episode_id", "patientId":"hospital_episodes.patient_id", "admittedAt":"hospital_episodes.admitted_at", "originMacro":"hospital_episodes.origin_macro", "originSite":"hospital_episodes.origin_site", "originWard":"hospital_episodes.origin_ward_legacy", "originWardId":"hospital_episodes.origin_ward_id", "currentWardId":"SOURCE_JSON (snapshot without effective date; not asserted as a movement)", "currentWardLabel":"SOURCE_JSON (snapshot without effective date; not asserted as a movement)", "currentWardLegacy":"SOURCE_JSON (snapshot without effective date; not asserted as a movement)", "wardHistory[]":"location_events (one row per documented movement)", "wardHistory[].enteredAt":"location_events.effective_at", "wardHistory[].exitedAt":"location_events.effective_to"},
    "cotConsultations": {"id":"consultations.consultation_id", "patientId":"consultations.patient_id", "hospitalEpisodeId":"consultations.episode_id", "pathwayId":"consultations.pathway_id", "requestedAt":"consultations.requested_at", "responseAt":"consultations.responded_at", "requester":"consultations.requester", "responseStatus":"consultations.response_status", "appropriateness":"consultations.appropriateness", "status":"consultations.status"},
    "dischargePathways": {"id":"pathways.pathway_id", "patientId":"pathways.patient_id", "hospitalEpisodeId":"pathways.episode_id", "target":"pathways.target", "requestedSettingId":"pathways.requested_setting_id", "requestedAt":"pathways.opened_at", "status":"pathways.administrative_status", "administrativelyClosedAt":"pathways.administratively_closed_at", "outcomeAt":"pathways.outcome_at", "closureReason":"pathways.closure_reason", "(pathway semantics)":"NO_AUTOMATIC_LINK; care_needs/pathway_needs require explicit reconciliation"},
    "odcWaitingList": {"id":"odc_waitlist.waitlist_id", "patientId":"odc_waitlist.patient_id", "pathwayId":"odc_waitlist.pathway_id", "unitId":"odc_waitlist.unit_id", "odcUnitId":"odc_waitlist.unit_id", "enteredAt":"odc_waitlist.entered_at", "plannedAdmissionAt":"odc_waitlist.planned_admission_at", "status":"odc_waitlist.status", "closedAt":"odc_waitlist.closed_at"},
    "odcStays": {"id":"odc_stays.stay_id", "patientId":"odc_stays.patient_id", "pathwayId":"odc_stays.pathway_id", "unitId":"odc_stays.unit_id", "odcUnitId":"odc_stays.unit_id", "admittedAt":"odc_stays.admitted_at", "plannedDischargeAt":"odc_stays.planned_discharge_at", "dischargedAt":"odc_stays.discharged_at", "plannedDestination":"odc_stays.planned_destination", "finalDestination":"odc_stays.final_destination"},
    "odcAssessments": {"id":"odc_assessments.assessment_id", "patientId":"odc_assessments.patient_id", "stayId":"odc_assessments.stay_id", "scale":"odc_assessments.scale", "phase":"odc_assessments.phase", "assessedAt":"odc_assessments.assessed_at", "score":"odc_assessments.score", "assessor":"odc_assessments.assessor", "(all assessment fields)":"odc_assessments.payload_json (lossless)"},
    "facilityContacts": {"id":"facility_requests.request_id", "patientId":"facility_requests (cross-check only)", "pathwayId":"facility_requests.pathway_id", "facilityId":"facility_requests.facility_id", "facilityLegacy":"facility_requests.facility_legacy", "facilityNameAtContact":"facility_requests (source JSON retained)", "method":"request_channels.channel", "methods[]":"request_channels (one row per channel)", "sentAt":"facility_requests.sent_at", "outcome":"facility_requests.initial_status", "responseAt":"facility_requests.response_at", "reason":"facility_requests.reason", "autoClosedByContactId":"facility_requests.auto_closed_by_request_id"},
    "events": {"id":"clinical_events.event_id", "patientId":"clinical_events.patient_id", "refType":"clinical_events.entity_type", "refId":"clinical_events.entity_id", "type":"clinical_events.event_type", "at":"clinical_events.effective_at", "recordedAt":"clinical_events.recorded_at", "actor":"clinical_events.operator", "meta":"clinical_events (typed extraction + source JSON retained)"},
    "audit": {"id":"audit_events.audit_id", "at":"audit_events.recorded_at", "action":"audit_events.action", "actor":"audit_events.operator", "(remaining fields)":"audit_events.payload_json"},
    "revisions": {"id":"revisions.revision_id", "entityType":"revisions.entity_type", "entityId":"revisions.entity_id", "effectiveAt":"revisions.effective_at", "recordedAt":"revisions.recorded_at", "actor":"revisions.operator", "reason":"revisions.reason", "before":"revisions.before_json", "after":"revisions.after_json"},
    "cotCases": {"id":"cot_cases.case_id", "patientId":"cot_cases.patient_id", "createdAt":"cot_cases.created_at", "createdBy":"cot_cases.created_by", "schemaVersion":"cot_cases.schema_version"},
    "cotCaseLinks": {"id":"cot_case_links.case_link_id", "patientId":"cot_case_links.patient_id", "cotCaseId":"cot_case_links.case_id", "entityType":"cot_case_links.entity_type", "entityId":"cot_case_links.entity_id", "relation":"cot_case_links.relation", "operation":"cot_case_links.operation", "effectiveDate":"cot_case_links.effective_at", "recordedAt":"cot_case_links.recorded_at", "source":"cot_case_links.source", "reason":"cot_case_links.reason", "supersedesId":"cot_case_links.supersedes_id", "schemaVersion":"cot_case_links.schema_version"},
    "cotCaseReconciliation": {"id":"cot_case_reconciliation.reconciliation_id", "patientId":"cot_case_reconciliation.patient_id", "entityType":"cot_case_reconciliation.entity_type", "entityId":"cot_case_reconciliation.entity_id", "decision":"cot_case_reconciliation.decision", "cotCaseId":"cot_case_reconciliation.case_id", "relation":"cot_case_reconciliation.relation", "source":"cot_case_reconciliation.source", "reason":"cot_case_reconciliation.reason", "recordedAt":"cot_case_reconciliation.recorded_at", "actor":"cot_case_reconciliation.actor", "supersedesId":"cot_case_reconciliation.supersedes_id", "schemaVersion":"cot_case_reconciliation.schema_version"},
    "config": {"facilities[]":"facilities + configuration_records", "wards[]":"wards + configuration_records", "settings[]":"settings + configuration_records", "odcUnits[]":"configuration_records", "contactHubs[]":"configuration_records", "italianMunicipalities[]":"configuration_records", "*":"configuration_records (unmodified JSON)"},
    "__meta__": {"*":"archive manifest/source metadata"},
    "__payload__": {"*":"complete source payload, immutable lossless reference"},
}


def empty_dataset() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **{name: [] for name in TABLES}}


def schema_manifest() -> dict[str, Any]:
    """Logical schema dictionary used by both file archive formats."""
    return {
        "schema_version": SCHEMA_VERSION,
        "table_count": len(TABLES),
        "source_staging_tables": list(SOURCE_STAGING_TABLES),
        "business_table_count": len(TABLES) - len(SOURCE_STAGING_TABLES),
        "source_staging_table_count": len(SOURCE_STAGING_TABLES),
        "id_encoding": "text",
        "date_encoding": "ISO-8601 text; no spreadsheet numeric dates",
        "tables": {
            name: {"columns": list(spec.columns), "primary_key": spec.key,
                   "required": list(spec.required), "date_columns": list(spec.dates),
                   "foreign_keys": [{"column": field, "references": parent, "nullable": nullable}
                                    for field, parent, nullable in spec.refs]}
            for name, spec in TABLES.items()
        },
        "r8_collections": {name: list(R8_TO_RELATIONAL[name]) for name in R8_TO_RELATIONAL},
        "preservation": "Every R8 payload and row is retained as canonical UTF-8 JSON in r8_source_records/r8_source_chunks; chunks are at most 30,000 characters for XLSX cell limits.",
    }


def _json_type(value: Any) -> str:
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, (int, float)): return "number"
    if isinstance(value, str): return "string"
    if isinstance(value, list): return "array"
    if isinstance(value, dict): return "object"
    return "unknown"


def _field_paths(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, _json_type(child)
            yield from _field_paths(child, path)
    elif isinstance(value, list):
        for child in value:
            yield from _field_paths(child, f"{prefix}[]")


SOURCE_CHUNK_CHARS = 30_000


def capture_r8_source(payload: dict[str, Any]) -> dict[str, Any]:
    """Losslessly stage every R8 row/config value without inferring clinical facts."""
    if not isinstance(payload, dict) or payload.get("version") != 3 or not isinstance(payload.get("meta"), dict) or payload["meta"].get("schema") != "COT_ODC_FLOW_V3_2":
        raise ValueError("È supportato solo il payload R8 V3.2")
    if not isinstance(payload.get("config"), dict): raise ValueError("config R8 deve essere un oggetto")
    missing = [name for name in R8_COLLECTIONS if not isinstance(payload.get(name), list)]
    if missing: raise ValueError("Raccolte R8 mancanti o non valide: " + ", ".join(missing))
    dataset = empty_dataset()
    seen_fields: dict[tuple[str, str], str] = {}
    raw_items: list[tuple[str, str, int, Any]] = [("__payload__", "payload", 0, payload), ("__meta__", "meta", 0, payload.get("meta", {})), ("config", "config", 0, payload.get("config", {}))]
    for key, rows in sorted((payload.get("config") or {}).items()):
        if isinstance(rows, list):
            for ordinal, row in enumerate(rows):
                if isinstance(row, dict): raw_items.append((f"config.{key}", str(row.get("id", "")), ordinal, row))
    for collection in R8_COLLECTIONS:
        rows = payload.get(collection, [])
        if not isinstance(rows, list):
            raise ValueError(f"La raccolta R8 {collection} non è una lista")
        for ordinal, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"{collection}[{ordinal}] non è un oggetto")
            source_id = row.get("id")
            raw_items.append((collection, str(source_id) if source_id is not None else "", ordinal, row))
    for collection, source_id, ordinal, row in raw_items:
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        key = f"SRC-{len(dataset['r8_source_records']) + 1:09d}"
        dataset["r8_source_records"].append({"source_record_key": key, "source_collection": collection,
            "source_id": source_id, "ordinal": str(ordinal),
            "json_chunk_count": str(max(1, (len(encoded) + SOURCE_CHUNK_CHARS - 1) // SOURCE_CHUNK_CHARS)),
            "sha256": sha256(encoded.encode("utf-8")).hexdigest()})
        for chunk_no, start in enumerate(range(0, len(encoded), SOURCE_CHUNK_CHARS), 1):
            dataset["r8_source_chunks"].append({"chunk_id": f"{key}-{chunk_no:06d}",
                "source_record_key": key, "chunk_no": str(chunk_no),
                "chunk_text": encoded[start:start + SOURCE_CHUNK_CHARS]})
        for path, typ in _field_paths(row):
            seen_fields[(collection, path)] = typ
    for (collection, path), typ in sorted(seen_fields.items()):
        key = f"FIELD-{len(dataset['r8_source_fields']) + 1:09d}"
        direct = R8_FIELD_MAPS.get(collection, {})
        mapped = direct.get(path, direct.get(path.split(".", 1)[0], "SOURCE_JSON (preserved; mapping reviewed per field)"))
        dataset["r8_source_fields"].append({"field_key": key, "source_collection": collection,
            "field_path": path, "json_type": typ, "mapped_to": mapped})
    _project_r8_payload(payload, dataset)
    return dataset


def _project_r8_payload(payload: dict[str, Any], dataset: dict[str, Any]) -> None:
    """Materialize typed, read-only projections; never infer care-need links."""
    source_keys = {(r["source_collection"], int(r["ordinal"])): r["source_record_key"]
                   for r in dataset["r8_source_records"]}

    def row_for(table: str, values: dict[str, Any], source_key: str | None):
        spec = TABLES[table]
        row = {column: None for column in spec.columns}
        row.update(values)
        if "source_record_id" in row: row["source_record_id"] = source_key
        dataset[table].append(row)
        return row

    def text(value):
        return None if value is None else str(value)

    def r8_rows(collection):
        return payload.get(collection, []) if isinstance(payload.get(collection, []), list) else []

    for ordinal, p in enumerate(r8_rows("patients")):
        row_for("patients", {"patient_id": text(p.get("id")), "tax_code": text(p.get("taxCode", p.get("cf"))),
            "surname": text(p.get("surname")), "given_name": text(p.get("name")), "birth_date": text(p.get("birthDate")),
            "residence_city": text(p.get("homeCity", p.get("residenceCity"))), "residence_province": text(p.get("homeProvince", p.get("residenceProvince"))),
            "residence_region": text(p.get("homeRegion", p.get("residenceRegion"))), "created_at": text(p.get("createdAt"))}, source_keys[("patients", ordinal)])

    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    facility_ids: set[str] = set()
    for ordinal, item in enumerate(config.get("facilities", []) if isinstance(config.get("facilities"), list) else []):
        if not isinstance(item, dict): continue
        facility_id = text(item.get("id"))
        if facility_id: facility_ids.add(facility_id)
        row_for("facilities", {"facility_id": facility_id, "name": text(item.get("name")), "kind": text(item.get("kind")),
            "city": text(item.get("city")), "province": text(item.get("province")), "region": text(item.get("region")),
            "active": item.get("active")}, source_keys.get(("config.facilities", ordinal)))
    ward_ids: set[str] = set()
    for ordinal, item in enumerate(config.get("wards", []) if isinstance(config.get("wards"), list) else []):
        if not isinstance(item, dict): continue
        ward_id = text(item.get("id"))
        if ward_id: ward_ids.add(ward_id)
        row_for("wards", {"ward_id": ward_id, "label": text(item.get("label", item.get("name"))),
            "facility_id": text(item.get("facilityId")) if text(item.get("facilityId")) in facility_ids else None,
            "active": item.get("active")}, source_keys.get(("config.wards", ordinal)))
    setting_ids: set[str] = set()
    for ordinal, item in enumerate(config.get("settings", []) if isinstance(config.get("settings"), list) else []):
        if not isinstance(item, dict): continue
        setting_id = text(item.get("id"))
        if setting_id: setting_ids.add(setting_id)
        row_for("settings", {"setting_id": setting_id, "code": text(item.get("code")), "label": text(item.get("label", item.get("name"))),
            "subtype": text(item.get("subtype"))}, source_keys.get(("config.settings", ordinal)))
    config_key = next((r["source_record_key"] for r in dataset["r8_source_records"] if r["source_collection"] == "config"), None)
    for ordinal, (key, value) in enumerate(sorted(config.items())):
        row_for("configuration_records", {"config_record_id": f"CFG-{ordinal + 1:06d}", "dictionary": str(key),
            "entry_id": None, "ordinal": str(ordinal), "value_json": json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))}, config_key)

    episode_ids: set[str] = set()
    for ordinal, item in enumerate(r8_rows("hospitalEpisodes")):
        episode_id = text(item.get("id"))
        if episode_id: episode_ids.add(episode_id)
        row_for("hospital_episodes", {"episode_id": episode_id, "patient_id": text(item.get("patientId")),
            "admitted_at": text(item.get("admittedAt")), "origin_macro": text(item.get("originMacro")),
            "origin_site": text(item.get("originSite")), "origin_ward_id": text(item.get("originWardId")) if text(item.get("originWardId")) in ward_ids else None,
            "origin_ward_legacy": text(item.get("originWard", item.get("admissionWardLabel"))), "legacy_status": text(item.get("status"))}, source_keys[("hospitalEpisodes", ordinal)])
        history = item.get("wardHistory") if isinstance(item.get("wardHistory"), list) else []
        for move_no, move in enumerate(history, 1):
            if not isinstance(move, dict): continue
            effective = text(move.get("enteredAt", move.get("effectiveAt")))
            if not effective: continue
            row_for("location_events", {"location_event_id": text(move.get("id")) or f"LOC-{episode_id}-{move_no:04d}",
                "patient_id": text(item.get("patientId")), "episode_id": episode_id, "facility_id": None,
                "facility_legacy": text(move.get("site")), "ward_id": text(move.get("wardId")) if text(move.get("wardId")) in ward_ids else None,
                "ward_legacy": text(move.get("ward", move.get("label"))), "effective_at": effective,
                "effective_to": text(move.get("exitedAt")), "recorded_at": text(move.get("recordedAt")),
                "status": "DOCUMENTED_LOCATION_INTERVAL" if move.get("exitedAt") else "LOCATION_END_NOT_DOCUMENTED",
                "source": text(move.get("provenance")) or "R8 hospitalEpisodes.wardHistory",
                "certainty": "DOCUMENTED", "notes": "Intervallo dallo storico R8; non equivale a verifica di presenza attuale."},
                source_keys[("hospitalEpisodes", ordinal)])

    pathway_ids: set[str] = set()
    for ordinal, item in enumerate(r8_rows("dischargePathways")):
        path_id = text(item.get("id"))
        if path_id: pathway_ids.add(path_id)
        status = text(item.get("status"))
        normalized_status = status if status in ("OPEN", "CLOSED", "CANCELLED", "UNVERIFIED") else "UNVERIFIED"
        row_for("pathways", {"pathway_id": path_id, "patient_id": text(item.get("patientId")),
            "episode_id": text(item.get("hospitalEpisodeId")) if text(item.get("hospitalEpisodeId")) in episode_ids else None,
            "target": text(item.get("target")), "requested_setting_id": text(item.get("requestedSettingId")) if text(item.get("requestedSettingId")) in setting_ids else None,
            "opened_at": text(item.get("requestedAt")), "administrative_status": normalized_status,
            "administratively_closed_at": text(item.get("administrativelyClosedAt", item.get("administrativeClosedAt"))),
            "outcome_at": text(item.get("outcomeAt")), "closure_reason": text(item.get("closureReason"))}, source_keys[("dischargePathways", ordinal)])

    for ordinal, item in enumerate(r8_rows("cotConsultations")):
        row_for("consultations", {"consultation_id": text(item.get("id")), "patient_id": text(item.get("patientId")),
            "episode_id": text(item.get("hospitalEpisodeId")) if text(item.get("hospitalEpisodeId")) in episode_ids else None,
            "pathway_id": text(item.get("pathwayId")) if text(item.get("pathwayId")) in pathway_ids else None,
            "requested_at": text(item.get("requestedAt")), "responded_at": text(item.get("responseAt")), "requester": text(item.get("requester")),
            "response_status": text(item.get("responseStatus")), "appropriateness": text(item.get("appropriateness")), "status": text(item.get("status"))},
            source_keys[("cotConsultations", ordinal)])

    contacts = r8_rows("facilityContacts")
    contact_ids = {text(item.get("id")) for item in contacts if item.get("id") is not None}
    request_state = {"in attesa": "AWAITING_RESPONSE", "nessun riscontro": "NO_RESPONSE", "accettato": "ACCEPTED", "richiesta ritirata": "WITHDRAWN"}
    for ordinal, item in enumerate(contacts):
        raw_status = text(item.get("outcome")) or "In attesa"
        folded = raw_status.casefold()
        state = request_state.get(folded, "REJECTED" if folded.startswith("rifiutat") else "TO_VERIFY")
        request_id = text(item.get("id"))
        facility_id = text(item.get("facilityId"))
        if facility_id not in facility_ids: facility_id = None
        close_id = text(item.get("autoClosedByContactId"))
        if close_id not in contact_ids: close_id = None
        row_for("facility_requests", {"request_id": request_id, "pathway_id": text(item.get("pathwayId")), "need_id": None,
            "facility_id": facility_id, "facility_legacy": text(item.get("facilityLegacy", item.get("facilityNameAtContact"))),
            "channel": text(item.get("method")), "sent_at": text(item.get("sentAt", item.get("dateSent"))), "initial_status": state,
            "response_at": text(item.get("responseAt")), "reason": text(item.get("reason", item.get("responseReason"))),
            "auto_closed_by_request_id": close_id, "certainty": "DOCUMENTED" if item.get("outcome") else "TO_VERIFY"}, source_keys[("facilityContacts", ordinal)])
        channels = item.get("methods") if isinstance(item.get("methods"), list) else []
        channel_values = list(dict.fromkeys(str(x) for x in channels if x not in (None, "")))
        if not channel_values and item.get("method"): channel_values = [str(item["method"])]
        for channel_no, channel in enumerate(channel_values, 1):
            row_for("request_channels", {"request_channel_id": f"CH-{request_id}-{channel_no:03d}", "request_id": request_id,
                "channel": channel, "effective_at": text(item.get("sentAt", item.get("dateSent")))}, source_keys[("facilityContacts", ordinal)])

    for ordinal, item in enumerate(r8_rows("odcWaitingList")):
        row_for("odc_waitlist", {"waitlist_id": text(item.get("id")), "patient_id": text(item.get("patientId")),
            "pathway_id": text(item.get("pathwayId")), "unit_id": text(item.get("odcUnitId", item.get("unitId"))),
            "entered_at": text(item.get("enteredAt")), "planned_admission_at": text(item.get("plannedAdmissionAt")),
            "status": text(item.get("status")), "closed_at": text(item.get("closedAt"))}, source_keys[("odcWaitingList", ordinal)])
    for ordinal, item in enumerate(r8_rows("odcStays")):
        row_for("odc_stays", {"stay_id": text(item.get("id")), "patient_id": text(item.get("patientId")),
            "pathway_id": text(item.get("pathwayId")), "unit_id": text(item.get("odcUnitId", item.get("unitId"))),
            "admitted_at": text(item.get("admittedAt")), "planned_discharge_at": text(item.get("plannedDischargeAt")),
            "discharged_at": text(item.get("dischargedAt")), "planned_destination": text(item.get("plannedDestination")),
            "final_destination": text(item.get("finalDestination"))}, source_keys[("odcStays", ordinal)])
    stay_ids = {row["stay_id"] for row in dataset["odc_stays"]}
    for ordinal, item in enumerate(r8_rows("odcAssessments")):
        row_for("odc_assessments", {"assessment_id": text(item.get("id")), "patient_id": text(item.get("patientId")),
            "stay_id": text(item.get("stayId")) if text(item.get("stayId")) in stay_ids else None, "scale": text(item.get("scale")),
            "phase": text(item.get("phase")), "assessed_at": text(item.get("assessedAt")), "score": item.get("score"),
            "assessor": text(item.get("assessor")), "payload_json": None}, source_keys[("odcAssessments", ordinal)])

    for ordinal, item in enumerate(r8_rows("events")):
        event_id = text(item.get("id")) or source_keys[("events", ordinal)]
        row_for("clinical_events", {"event_id": event_id, "patient_id": text(item.get("patientId")),
            "entity_type": text(item.get("refType")), "entity_id": text(item.get("refId")), "event_type": text(item.get("type")) or "TO_VERIFY",
            "effective_at": text(item.get("at")), "recorded_at": text(item.get("recordedAt")), "operator": text(item.get("actor")),
            "reason": text(item.get("reason")), "source": text(item.get("source")), "certainty": "TO_VERIFY",
            "notes": text(item.get("label")), "source_record_id": source_keys[("events", ordinal)]}, None)
    for collection, table, id_col in (("audit", "audit_events", "audit_id"), ("revisions", "revisions", "revision_id"),
            ("cotCases", "cot_cases", "case_id"), ("cotCaseLinks", "cot_case_links", "case_link_id"),
            ("cotCaseReconciliation", "cot_case_reconciliation", "reconciliation_id")):
        for ordinal, item in enumerate(r8_rows(collection)):
            key = source_keys[(collection, ordinal)]
            value_map = {
                "audit": {"audit_id": text(item.get("id")) or key, "recorded_at": text(item.get("at", item.get("recordedAt"))),
                    "operator": text(item.get("actor")), "action": text(item.get("action")) or "TO_VERIFY", "entity_type": text(item.get("entityType")),
                    "entity_id": text(item.get("entityId")), "reason": text(item.get("reason")), "payload_json": json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
                "revisions": {"revision_id": text(item.get("id")) or key, "entity_type": text(item.get("entityType")) or "TO_VERIFY",
                    "entity_id": text(item.get("entityId")) or "TO_VERIFY", "effective_at": text(item.get("effectiveAt")),
                    "recorded_at": text(item.get("recordedAt", item.get("at"))), "operator": text(item.get("actor")), "reason": text(item.get("reason")),
                    "before_json": json.dumps(item.get("before"), ensure_ascii=False, sort_keys=True, separators=(",", ":")) if "before" in item else None,
                    "after_json": json.dumps(item.get("after"), ensure_ascii=False, sort_keys=True, separators=(",", ":")) if "after" in item else None,
                    "supersedes_id": text(item.get("supersedesId"))},
                "cotCases": {"case_id": text(item.get("id")), "patient_id": text(item.get("patientId")), "created_at": text(item.get("createdAt")),
                    "created_by": text(item.get("createdBy")), "schema_version": item.get("schemaVersion")},
                "cotCaseLinks": {"case_link_id": text(item.get("id")), "patient_id": text(item.get("patientId")), "case_id": text(item.get("cotCaseId")),
                    "entity_type": text(item.get("entityType")), "entity_id": text(item.get("entityId")), "relation": text(item.get("relation")),
                    "operation": text(item.get("operation")), "effective_at": text(item.get("effectiveDate")), "recorded_at": text(item.get("recordedAt")),
                    "source": text(item.get("source")), "reason": text(item.get("reason")), "supersedes_id": text(item.get("supersedesId")),
                    "schema_version": item.get("schemaVersion")},
                "cotCaseReconciliation": {"reconciliation_id": text(item.get("id")), "patient_id": text(item.get("patientId")),
                    "entity_type": text(item.get("entityType")), "entity_id": text(item.get("entityId")), "decision": text(item.get("decision")),
                    "case_id": text(item.get("cotCaseId")), "relation": text(item.get("relation")), "source": text(item.get("source")),
                    "reason": text(item.get("reason")), "recorded_at": text(item.get("recordedAt")), "actor": text(item.get("actor")),
                    "supersedes_id": text(item.get("supersedesId")), "schema_version": item.get("schemaVersion")},
            }[collection]
            row_for(table, value_map, key)


def restore_source_record(dataset: dict[str, Any], source_record_key: str) -> Any:
    """Reassemble one staged source JSON value and check its content hash."""
    header = next((r for r in dataset.get("r8_source_records", []) if r.get("source_record_key") == source_record_key), None)
    if header is None:
        raise KeyError(source_record_key)
    chunks = sorted((r for r in dataset.get("r8_source_chunks", []) if r.get("source_record_key") == source_record_key), key=lambda r: int(r["chunk_no"]))
    encoded = "".join(r["chunk_text"] for r in chunks)
    if len(chunks) != int(header["json_chunk_count"]) or sha256(encoded.encode("utf-8")).hexdigest() != header["sha256"]:
        raise ValueError(f"Sorgente incompleta o checksum errato: {source_record_key}")
    return json.loads(encoded)


R8_PROJECTION_TABLES = tuple(name for name in TABLES if name not in (
    "care_needs", "pathway_needs", "request_events"))


def reconstruct_r8_payload(dataset: dict[str, Any]) -> dict[str, Any]:
    issues = validate_dataset(dataset) + validate_r8_projection(dataset)
    if issues:
        raise ValueError("Archivio relazionale non ricostruibile: " + "; ".join(issues[:8]))
    root = next((row for row in dataset["r8_source_records"] if row["source_collection"] == "__payload__"), None)
    if root is None:
        raise ValueError("Payload R8 sorgente mancante")
    payload = restore_source_record(dataset, root["source_record_key"])
    if not isinstance(payload, dict):
        raise ValueError("Payload R8 sorgente non è un oggetto")
    return payload


def validate_r8_projection(dataset: dict[str, Any]) -> list[str]:
    """Reject divergent typed rows; R8 source is canonical until a writer exists."""
    try:
        payload_row = next(row for row in dataset.get("r8_source_records", []) if row.get("source_collection") == "__payload__")
        payload = restore_source_record(dataset, payload_row["source_record_key"])
        projected = capture_r8_source(payload)
    except (StopIteration, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [f"Payload R8 sorgente non verificabile: {exc}"]
    errors = []
    for table in R8_PROJECTION_TABLES:
        if dataset.get(table) != projected.get(table):
            errors.append(f"{table}: proiezione diversa dal payload canonico; usare la modifica write-through")
    # These extension tables have no lossless representation in R8 V3.2 yet.
    for table in ("care_needs", "pathway_needs", "request_events"):
        if dataset.get(table): errors.append(f"{table}: dati senza rappresentazione R8 V3.2; esportazione bloccata")
    return errors


def edit_r8_field(dataset: dict[str, Any], collection: str, source_id: str, field: str, value: Any) -> dict[str, Any]:
    """Write through a mapped, existing R8 field, then regenerate all projections."""
    target = R8_FIELD_MAPS.get(collection, {}).get(field, "")
    if "." not in target or "(" in target or target.startswith("SOURCE_JSON"):
        raise ValueError(f"Campo non modificabile tramite mapping tipizzato: {collection}.{field}")
    table, column = target.split(".", 1)
    if table not in TABLES or column not in TABLES[table].columns or column.endswith("_id"):
        raise ValueError(f"Campo non modificabile o identificativo: {collection}.{field}")
    payload = reconstruct_r8_payload(dataset)
    rows = payload.get(collection)
    if not isinstance(rows, list): raise ValueError(f"Raccolta assente: {collection}")
    matches = [row for row in rows if isinstance(row, dict) and str(row.get("id", "")) == str(source_id)]
    if len(matches) != 1: raise ValueError(f"Record sorgente non univoco o assente: {collection}/{source_id}")
    source_row = matches[0]
    if field not in source_row: raise ValueError(f"Campo sorgente assente; non viene creato implicitamente: {collection}.{field}")
    if value is not None and not isinstance(value, type(source_row[field])):
        raise TypeError(f"Tipo incompatibile per {collection}.{field}: atteso {type(source_row[field]).__name__}")
    source_row[field] = value
    updated = capture_r8_source(payload)
    issues = validate_dataset(updated) + validate_r8_projection(updated)
    if issues: raise ValueError("Modifica rifiutata: " + "; ".join(issues[:8]))
    return updated


def _date_ok(value: Any) -> bool:
    if value in (None, ""): return True
    if not isinstance(value, str): return False
    try:
        if "T" in value: datetime.fromisoformat(value.replace("Z", "+00:00"))
        else: date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    """Return deterministic schema, key, date, and FK errors; never auto-correct."""
    errors: list[str] = []
    if not isinstance(dataset, dict) or dataset.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version deve essere {SCHEMA_VERSION}"]
    indexes: dict[str, dict[str, dict[str, Any]]] = {}
    for name, spec in TABLES.items():
        rows = dataset.get(name)
        if not isinstance(rows, list):
            errors.append(f"{name}: tabella mancante o non lista")
            continue
        index: dict[str, dict[str, Any]] = {}
        indexes[name] = index
        allowed = set(spec.columns)
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                errors.append(f"{name}[{i}]: riga non oggetto")
                continue
            extra = set(row) - allowed
            if extra: errors.append(f"{name}[{i}]: colonne non dichiarate {sorted(extra)}")
            for field in spec.required:
                if row.get(field) in (None, ""):
                    errors.append(f"{name}[{i}]: {field} obbligatorio")
            key = row.get(spec.key)
            if key not in (None, ""):
                key = str(key)
                if key in index: errors.append(f"{name}[{i}]: ID duplicato {key}")
                else: index[key] = row
            for field in spec.dates:
                if not _date_ok(row.get(field)):
                    errors.append(f"{name}[{i}]: data non ISO in {field}")
            for field, values in spec.choices:
                value = row.get(field)
                if value not in (None, "") and value not in values:
                    errors.append(f"{name}[{i}]: valore {value!r} non ammesso in {field}")
    for name, spec in TABLES.items():
        if name not in indexes: continue
        for i, row in enumerate(dataset[name], 1):
            if not isinstance(row, dict): continue
            for field, parent, nullable in spec.refs:
                value = row.get(field)
                if value in (None, "") and nullable: continue
                if str(value) not in indexes.get(parent, {}):
                    errors.append(f"{name}[{i}]: {field}={value!r} senza riferimento in {parent}")
    # Patient identity must agree across the pathway↔need relation.
    paths, needs = indexes.get("pathways", {}), indexes.get("care_needs", {})
    for i, link in enumerate(dataset.get("pathway_needs", []), 1):
        p, n = paths.get(str(link.get("pathway_id"))), needs.get(str(link.get("need_id")))
        if p and n and p.get("patient_id") != n.get("patient_id"):
            errors.append(f"pathway_needs[{i}]: percorso e bisogno appartengono a pazienti diversi")
    episodes = indexes.get("hospital_episodes", {})
    for table_name in ("consultations", "pathways", "odc_waitlist", "odc_stays", "location_events"):
        for i, row in enumerate(dataset.get(table_name, []), 1):
            episode_id = row.get("episode_id")
            episode = episodes.get(str(episode_id)) if episode_id not in (None, "") else None
            if episode and row.get("patient_id") != episode.get("patient_id"):
                errors.append(f"{table_name}[{i}]: episodio e paziente non corrispondono")
    for table_name in ("odc_waitlist", "odc_stays"):
        for i, row in enumerate(dataset.get(table_name, []), 1):
            path = paths.get(str(row.get("pathway_id")))
            if path and row.get("patient_id") != path.get("patient_id"):
                errors.append(f"{table_name}[{i}]: percorso e paziente non corrispondono")
    # A request must belong to the same patient as its pathway and optional need.
    patients = indexes.get("patients", {})
    for i, request in enumerate(dataset.get("facility_requests", []), 1):
        p = paths.get(str(request.get("pathway_id")))
        need_id = request.get("need_id")
        n = needs.get(str(need_id)) if need_id not in (None, "") else None
        if p and n and p.get("patient_id") != n.get("patient_id"):
            errors.append(f"facility_requests[{i}]: richiesta lega percorso e bisogno di pazienti diversi")
        if p and p.get("patient_id") not in patients:
            errors.append(f"facility_requests[{i}]: paziente del percorso non risolto")
    source_rows = indexes.get("r8_source_records", {})
    chunk_groups: dict[str, list[dict[str, Any]]] = {}
    for i, chunk in enumerate(dataset.get("r8_source_chunks", []), 1):
        owner = str(chunk.get("source_record_key", ""))
        chunk_groups.setdefault(owner, []).append(chunk)
        try:
            if int(chunk.get("chunk_no", "")) < 1: raise ValueError
        except (TypeError, ValueError):
            errors.append(f"r8_source_chunks[{i}]: chunk_no non valido")
        if len(str(chunk.get("chunk_text", ""))) > SOURCE_CHUNK_CHARS:
            errors.append(f"r8_source_chunks[{i}]: chunk oltre il limite XLSX")
    for key, header in source_rows.items():
        chunks = sorted(chunk_groups.get(key, []), key=lambda row: int(row.get("chunk_no", 0) or 0))
        try:
            expected = int(header.get("json_chunk_count", ""))
            numbers = [int(row["chunk_no"]) for row in chunks]
            encoded = "".join(str(row.get("chunk_text", "")) for row in chunks)
            if len(chunks) != expected or numbers != list(range(1, expected + 1)):
                errors.append(f"r8_source_records/{key}: sequenza chunk incompleta o duplicata")
            elif sha256(encoded.encode("utf-8")).hexdigest() != header.get("sha256"):
                errors.append(f"r8_source_records/{key}: checksum non corrispondente")
            else:
                json.loads(encoded)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            errors.append(f"r8_source_records/{key}: JSON/chunk non valido")
    for key in set(chunk_groups) - set(source_rows):
        errors.append(f"r8_source_chunks: record sorgente inesistente {key}")
    # Multiple OPEN pathways and multiple active candidate structures are allowed.
    return errors
