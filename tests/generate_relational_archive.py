"""Write a repeatable synthetic COT file archive outside the repository."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from relational_fixture import make_payload
from relational_session import export_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("ZIP/CSV", "XLSX"), default="ZIP/CSV")
    args = parser.parse_args()
    exported = export_payload(make_payload(), args.format, "COT_CICLO6_SINTETICO")
    suffix = ".zip" if args.format == "ZIP/CSV" else ".xlsx"
    fd, name = tempfile.mkstemp(prefix="cot-ciclo6-sintetico-", suffix=suffix)
    path = Path(name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(exported.content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    print(f"{path}\nSHA-256 {exported.sha256}\n20 pazienti sintetici; nessun dato operativo")


if __name__ == "__main__":
    main()
