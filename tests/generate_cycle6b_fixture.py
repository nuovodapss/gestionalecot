"""Create a disposable 20-patient relational archive for the Cycle 6B browser run."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from relational_session import export_payload
from relational_fixture import make_payload


def make_cycle6b_payload() -> dict:
    payload = make_payload(patient_count=20, long_text_repeat=20)
    payload["facilityContacts"] = [
        {
            "id": f"TEST-C6B-FC-{index:02d}",
            "patientId": "TEST-PAT-0001",
            "pathwayId": "TEST-PATH-0001-A",
            "facilityId": f"TEST-FAC-{index:02d}",
            "facilityNameAtContact": f"Struttura sintetica {index}",
            "method": "PEC",
            "methods": ["PEC"],
            "sentAt": f"2026-11-{index + 1:02d}",
            "responseAt": "",
            "outcome": "In attesa",
            "reason": "Contatto sintetico per test Cycle 6B",
            "createdAt": "2026-11-18T08:00:00.000Z",
        }
        for index in range(1, 4)
    ] + [
        {
            "id": "TEST-C6B-FC-04",
            "patientId": "TEST-PAT-0001",
            "pathwayId": "TEST-PATH-0001-B",
            "facilityId": "TEST-FAC-04",
            "facilityNameAtContact": "Struttura sintetica 4",
            "method": "PEC",
            "methods": ["PEC"],
            "sentAt": "2026-11-05",
            "responseAt": "",
            "outcome": "In attesa",
            "reason": "Richiesta sul percorso indipendente",
            "createdAt": "2026-11-18T08:00:00.000Z",
        }
    ]
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for file_format, extension in (("ZIP/CSV", "zip"), ("XLSX", "xlsx")):
        exported = export_payload(make_cycle6b_payload(), file_format, f"cot_cycle6b_synthetic")
        target = args.directory / f"cycle6b_synthetic.{extension}"
        target.write_bytes(exported.content)
        target.chmod(0o600)
        print(f"{target} {len(exported.content)} bytes SHA-256 {exported.sha256}")


if __name__ == "__main__":
    main()
