"""Consistent local SQLite snapshot using the backup API. Prototype only."""
from datetime import datetime
from pathlib import Path
import sqlite3

import database as db

def backup():
    if not db.DB_PATH.is_file():
        raise FileNotFoundError('Database non ancora creato: avviare prima Streamlit')
    outdir=Path(__file__).resolve().parent/'backup_locali'
    outdir.mkdir(exist_ok=True)
    dest=outdir/f"cot_v02_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    with sqlite3.connect(db.DB_PATH) as origin, sqlite3.connect(dest) as copy:
        origin.backup(copy)
    print(f'Backup SQLite coerente salvato in: {dest}')
    print('ATTENZIONE: questa copia non è cifrata e non costituisce backup aziendale.')
    return dest

if __name__=='__main__':backup()
