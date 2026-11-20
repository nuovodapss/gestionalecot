"""Deterministic R8 V3.2-shaped synthetic payload for file archive tests."""

def make_payload(patient_count=20, long_text_repeat=1200):
    patients = [{"id": f"TEST-PAT-{i:04d}", "taxCode": f"000000000{i:06d}",
        "surname": f"PAZIENTE TEST {i:02d}", "name": f"SINTETICO {i:02d}", "birthDate": f"195{i % 10}-01-02",
        "homeCity": "Città di prova", "homeProvince": "TT", "homeRegion": "Regione test",
        "createdAt": "2026-11-18T08:00:00.000Z", "nullable": None, "empty": "", "zero": 0,
        "active": False, "extraField": {"nested": [1, "é", None]},
        "longFreeText": "Nota sintetica: àèìòù; | #\n" + ("nessun dato sanitario reale. " * long_text_repeat)} for i in range(1, patient_count + 1)]
    facilities = [{"id": f"TEST-FAC-{i:02d}", "name": f"Struttura sintetica {i}", "kind": "TEST",
        "city": "Città di prova", "province": "TT", "region": "Test", "active": True,
        "extra": {"numericCode": "0007", "marker": "& < > ="}} for i in range(1, 5)]
    wards = [{"id": "TEST-WARD-01", "label": "Reparto sintetico Medicina", "facilityId": None, "active": True}]
    settings = [{"id": "TEST-SETTING-01", "code": "056", "label": "Riabilitazione sintetica", "subtype": "TEST"},
                {"id": "TEST-SETTING-HOSP", "code": "", "label": "Hospice test", "subtype": "TEST"}]
    episodes = [{"id": f"TEST-EP-{i:04d}", "patientId": patients[i-1]["id"], "admittedAt": "2026-11-01",
        "status": "OPEN", "originMacro": "TEST", "originSite": "SITE-01", "originWardId": "TEST-WARD-01",
        "originWard": "Reparto sintetico Medicina", "currentWardId": "TEST-WARD-01",
        "wardHistory": [{"id": f"TEST-LOC-{i:04d}-1", "enteredAt": "2026-11-01", "exitedAt": "2026-11-04",
                         "wardId": "TEST-WARD-01", "ward": "Reparto sintetico Medicina", "provenance": "fixture"},
                        {"id": f"TEST-LOC-{i:04d}-2", "enteredAt": "2026-11-04", "exitedAt": "",
                         "wardId": "TEST-WARD-01", "ward": "Reparto sintetico Medicina", "provenance": "fixture"}],
        "unknownEpisodeField": {"stay": None}} for i in range(1, min(patient_count, 14) + 1)]
    pathways = []
    for i, patient in enumerate(patients, 1):
        episode = episodes[i-1]["id"] if i <= len(episodes) else None
        pathways.append({"id": f"TEST-PATH-{i:04d}-A", "patientId": patient["id"], "hospitalEpisodeId": episode,
            "status": "OPEN", "target": "EXTERNAL", "requestedAt": "2026-11-03", "requestedSettingId": "TEST-SETTING-01",
            "outcomeAt": None, "fktRequired": "YES", "fktStatus": "IN_CORSO", "priamoStatus": "VALID",
            "hospice": False, "special": "Ω"})
        if i in (1, 2, 3):
            pathways.append({"id": f"TEST-PATH-{i:04d}-B", "patientId": patient["id"], "hospitalEpisodeId": episode,
                "status": "OPEN", "target": "HOSPICE" if i == 2 else "ODC", "requestedAt": "2026-11-05",
                "requestedSettingId": "TEST-SETTING-HOSP" if i == 2 else "TEST-SETTING-01", "outcomeAt": None,
                "note": "Percorso parallelo; non un duplicato."})
    cot = [{"id": f"TEST-COT-{i:04d}", "patientId": patients[i-1]["id"], "hospitalEpisodeId": episodes[i-1]["id"],
        "pathwayId": f"TEST-PATH-{i:04d}-A", "requestedAt": "2026-11-03", "responseAt": None,
        "responseStatus": "PENDING", "appropriateness": "YES", "requester": "TEST", "status": "OPEN"} for i in range(1, min(7, patient_count + 1))]
    contacts = []
    for i, state in enumerate(("In attesa", "Nessun riscontro", "Accettato", "Rifiutato - criteri sintetici"), 1):
        contacts.append({"id": f"TEST-FC-{i:04d}", "patientId": patients[0]["id"], "pathwayId": "TEST-PATH-0001-A",
            "facilityId": facilities[i-1]["id"], "facilityNameAtContact": facilities[i-1]["name"], "method": "PEC",
            "methods": ["PEC", "Telefono"] if i == 1 else ["PEC"], "sentAt": f"2026-11-{i+5:02d}",
            "responseAt": "2026-11-12" if state.startswith(("Accettato", "Rifiutato")) else "", "outcome": state,
            "reason": "Motivo prova — non reale", "createdAt": "2026-11-10T08:00:00.000Z", "extended": [None, 3, True]})
    waitlist = [{"id": "TEST-WAIT-01", "patientId": patients[1]["id"], "pathwayId": "TEST-PATH-0002-B", "odcUnitId": "TEST-ODC",
        "enteredAt": "2026-11-10", "plannedAdmissionAt": "2026-11-19", "status": "PLANNED", "closedAt": ""}]
    stays = [{"id": "TEST-STAY-01", "patientId": patients[2]["id"], "pathwayId": "TEST-PATH-0003-B", "odcUnitId": "TEST-ODC",
        "admittedAt": "2026-11-11", "plannedDischargeAt": "2026-11-25", "dischargedAt": None,
        "plannedDestination": "Destinazione test", "finalDestination": None}]
    assessments = [{"id": "TEST-ASSESS-01", "patientId": patients[2]["id"], "stayId": "TEST-STAY-01", "scale": "ICA",
        "phase": "INGRESSO", "assessedAt": "2026-11-11", "score": 4.5, "assessor": "TEST",
        "items": {"01": 0, "02": None, "notes": "Longitudinale sintetico"}}]
    events = [{"id": f"TEST-EV-{i:04d}", "type": "PRIAMO_UPDATED" if i == 1 else "FKT_UPDATED", "patientId": patients[0]["id"],
        "refType": "dischargePathway", "refId": "TEST-PATH-0001-A", "at": f"2026-11-{i+5:02d}T09:30:00.000Z",
        "recordedAt": f"2026-11-{i+5:02d}T10:00:00.000Z", "actor": "TEST", "label": "Evento sintetico",
        "meta": {"old": None, "new": {"valid": True, "code": "0009"}, "special": "àèìòù Ω / | #\n" + ("evento sintetico. " * 1600)}} for i in range(1, 5)]
    audit = [{"id": "TEST-AUD-01", "at": "2026-11-18T12:00:00.000Z", "action": "SYNTHETIC_TEST", "actor": "TEST", "payload": {"kept": True}}]
    revisions = [{"id": "TEST-REV-01", "entityType": "patient", "entityId": patients[0]["id"], "effectiveAt": "2026-11-10",
        "recordedAt": "2026-11-18T12:00:00.000Z", "actor": "TEST", "reason": "Rettifica sintetica",
        "before": {"name": "SINTETICO", "id": "0007"}, "after": {"name": "SINTETICO MODIFICATO", "nullable": None}}]
    cases = [{"id": "TEST-CASE-01", "patientId": patients[0]["id"], "createdAt": "2026-11-18T12:00:00.000Z", "createdBy": "TEST", "schemaVersion": 1}]
    links = [{"id": "TEST-LINK-01", "patientId": patients[0]["id"], "cotCaseId": "TEST-CASE-01", "entityType": "dischargePathway",
        "entityId": "TEST-PATH-0001-A", "relation": "OWNER", "operation": "ATTACH", "effectiveDate": None,
        "recordedAt": "2026-11-18T12:00:00.000Z", "source": "SYNTHETIC", "reason": "test", "supersedesId": None, "schemaVersion": 1}]
    reconciliation = [{"id": "TEST-RECON-01", "patientId": patients[0]["id"], "entityType": "dischargePathway", "entityId": "TEST-PATH-0001-A",
        "decision": "ASSIGNED", "cotCaseId": "TEST-CASE-01", "relation": "OWNER", "source": "SYNTHETIC", "reason": "test",
        "recordedAt": "2026-11-18T12:00:00.000Z", "actor": "TEST", "supersedesId": None, "schemaVersion": 1}]
    return {"version": 3, "meta": {"schema": "COT_ODC_FLOW_V3_2", "createdAt": "2026-11-01T00:00:00.000Z",
            "updatedAt": "2026-11-18T12:00:00.000Z", "unknownMeta": [None, "Ω"]},
        "config": {"facilities": facilities, "wards": wards, "settings": settings,
            "odcUnits": [{"id": "TEST-ODC", "name": "OdC sintetico", "active": True}], "futureDictionary": {"alpha": [1, None, "é"]}},
        "patients": patients, "hospitalEpisodes": episodes, "cotConsultations": cot, "dischargePathways": pathways,
        "odcWaitingList": waitlist, "odcStays": stays, "odcAssessments": assessments, "facilityContacts": contacts,
        "events": events, "audit": audit, "revisions": revisions, "cotCases": cases,
        "cotCaseLinks": links, "cotCaseReconciliation": reconciliation,
        "futureRootField": {"mustSurvive": True, "idLike": "0007"}}
