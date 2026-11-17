"""COT v0.3 - clinical data model sandbox; SQLite is for local testing ONLY.

Patients -> multiple concurrently open pathways; needs -> multiple concurrently open
pathways (via links), and needs -> multiple simultaneous facility requests.
An accepted facility atomically closes the OTHER active requests for the same need,
without closing independent pathways or needs. Acceptance is not physical admission.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("COT_DB_PATH", ROOT / "data" / "cot_v03.db"))

TABLE_COLUMNS = {
    "PAZIENTI": ["id_paziente", "cognome", "nome", "codice_fiscale", "data_nascita"],
    "STRUTTURE": ["id_struttura", "denominazione", "tipologia", "comune"],
    "PERCORSI": ["id_percorso", "id_paziente", "data_attivazione", "provenienza", "presidio", "reparto", "data_ricovero", "stato_iniziale", "note"],
    "BISOGNI": ["id_bisogno", "id_paziente", "setting_iniziale", "data_inizio", "stato_iniziale", "note"],
    "PERCORSI_BISOGNI": ["id_collegamento", "id_percorso", "id_bisogno", "data_collegamento", "operatore"],
    "RICHIESTE": ["id_richiesta", "id_bisogno", "id_struttura", "data_richiesta", "stato_iniziale", "canali_iniziali", "note", "operatore"],
    "EVENTI_PERCORSO": ["id_evento", "id_percorso", "data_evento", "stato", "note", "operatore", "registrato_il"],
    "EVENTI_BISOGNO": ["id_evento", "id_bisogno", "data_evento", "tipo_evento", "valore", "note", "operatore", "registrato_il"],
    "EVENTI_RICHIESTA": ["id_evento", "id_richiesta", "data_evento", "stato", "canali", "note", "operatore", "registrato_il"],
    "COLLOCAZIONI": ["id_evento", "id_paziente", "data_evento", "presidio", "reparto", "struttura", "stato", "note", "operatore", "registrato_il"],
    "VERIFICHE": ["id_verifica", "id_bisogno", "data_evento", "esito", "fonte", "note", "operatore", "registrato_il"],
}
TABLE_SQL = {
    "PAZIENTI": "patients", "STRUTTURE": "facilities", "PERCORSI": "pathways", "BISOGNI": "needs",
    "PERCORSI_BISOGNI": "path_need_links", "RICHIESTE": "requests", "EVENTI_PERCORSO": "path_events",
    "EVENTI_BISOGNO": "need_events", "EVENTI_RICHIESTA": "request_events", "COLLOCAZIONI": "location_events", "VERIFICHE": "reviews",
}
TABLE_KEYS = {label: columns[0] for label, columns in TABLE_COLUMNS.items()}
IMPORT_ORDER = tuple(TABLE_COLUMNS)
EVENT_TABLES = ("EVENTI_PERCORSO", "EVENTI_BISOGNO", "EVENTI_RICHIESTA", "COLLOCAZIONI", "VERIFICHE")
PATH_STATES = ("OPEN", "CLOSED", "CANCELLED")
NEED_STATES = ("APERTA", "SOSPESA", "CONCLUSA", "ANNULLATA")
REQ_STATES = ("INVIATA", "ATTENZIONATA", "ATTRIBUITA", "IN_ATTESA_RISPOSTA", "ACCETTATA", "RIFIUTATA", "RITIRATA", "CHIUSA_PER_ALTRA_ACCETTAZIONE", "INGRESSO_CONFERMATO")
ACTIVE_REQ_STATES = frozenset(("INVIATA", "ATTENZIONATA", "ATTRIBUITA", "IN_ATTESA_RISPOSTA", "ACCETTATA"))
TERMINAL_REQ_STATES = frozenset(("RIFIUTATA", "RITIRATA", "CHIUSA_PER_ALTRA_ACCETTAZIONE", "INGRESSO_CONFERMATO"))
CHANNELS = ("Attribuzione", "Attenzionamento", "Altro canale")
NEED_EVENT_KINDS = ("STATO", "ATTESA_INIZIO", "ATTESA_FINE", "SETTING", "DIMISSIBILITA", "NOTA")
REVIEW_RESULTS = ("ATTESA_CONFERMATA", "ATTESA_DOCUMENTALE", "NON_IN_ATTESA", "DA_VERIFICARE")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:18].upper()}"


def iso(d: date | str | None) -> str:
    if not d:
        return ""
    result = str(d)[:10]
    try:
        date.fromisoformat(result)
    except ValueError as exc:
        raise ValueError(f"Data non valida: {d}") from exc
    return result


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id_paziente TEXT PRIMARY KEY, cognome TEXT NOT NULL, nome TEXT NOT NULL,
            codice_fiscale TEXT NOT NULL DEFAULT '', data_nascita TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS facilities (
            id_struttura TEXT PRIMARY KEY, denominazione TEXT NOT NULL,
            tipologia TEXT NOT NULL DEFAULT '', comune TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pathways (
            id_percorso TEXT PRIMARY KEY, id_paziente TEXT NOT NULL REFERENCES patients(id_paziente),
            data_attivazione TEXT NOT NULL, provenienza TEXT NOT NULL, presidio TEXT NOT NULL DEFAULT '',
            reparto TEXT NOT NULL DEFAULT '', data_ricovero TEXT NOT NULL DEFAULT '',
            stato_iniziale TEXT NOT NULL DEFAULT 'OPEN', note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS needs (
            id_bisogno TEXT PRIMARY KEY, id_paziente TEXT NOT NULL REFERENCES patients(id_paziente),
            setting_iniziale TEXT NOT NULL, data_inizio TEXT NOT NULL,
            stato_iniziale TEXT NOT NULL DEFAULT 'APERTA', note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS path_need_links (
            id_collegamento TEXT PRIMARY KEY, id_percorso TEXT NOT NULL REFERENCES pathways(id_percorso),
            id_bisogno TEXT NOT NULL REFERENCES needs(id_bisogno),
            data_collegamento TEXT NOT NULL, operatore TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests (
            id_richiesta TEXT PRIMARY KEY, id_bisogno TEXT NOT NULL REFERENCES needs(id_bisogno),
            id_struttura TEXT NOT NULL REFERENCES facilities(id_struttura),
            data_richiesta TEXT NOT NULL, stato_iniziale TEXT NOT NULL DEFAULT 'INVIATA', canali_iniziali TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '', operatore TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS path_events (
            id_evento TEXT PRIMARY KEY, id_percorso TEXT NOT NULL REFERENCES pathways(id_percorso),
            data_evento TEXT NOT NULL, stato TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
            operatore TEXT NOT NULL, registrato_il TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS need_events (
            id_evento TEXT PRIMARY KEY, id_bisogno TEXT NOT NULL REFERENCES needs(id_bisogno),
            data_evento TEXT NOT NULL, tipo_evento TEXT NOT NULL, valore TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '', operatore TEXT NOT NULL, registrato_il TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS request_events (
            id_evento TEXT PRIMARY KEY, id_richiesta TEXT NOT NULL REFERENCES requests(id_richiesta),
            data_evento TEXT NOT NULL, stato TEXT NOT NULL, canali TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '', operatore TEXT NOT NULL, registrato_il TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS location_events (
            id_evento TEXT PRIMARY KEY, id_paziente TEXT NOT NULL REFERENCES patients(id_paziente),
            data_evento TEXT NOT NULL, presidio TEXT NOT NULL DEFAULT '',
            reparto TEXT NOT NULL DEFAULT '', struttura TEXT NOT NULL DEFAULT '',
            stato TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
            operatore TEXT NOT NULL, registrato_il TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id_verifica TEXT PRIMARY KEY, id_bisogno TEXT NOT NULL REFERENCES needs(id_bisogno),
            data_evento TEXT NOT NULL, esito TEXT NOT NULL, fonte TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '', operatore TEXT NOT NULL, registrato_il TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_path_patient ON pathways(id_paziente);
        CREATE INDEX IF NOT EXISTS idx_need_patient ON needs(id_paziente);
        CREATE INDEX IF NOT EXISTS idx_links_need ON path_need_links(id_bisogno, data_collegamento);
        CREATE INDEX IF NOT EXISTS idx_links_path ON path_need_links(id_percorso);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_links_unique ON path_need_links(id_percorso,id_bisogno);
        CREATE INDEX IF NOT EXISTS idx_requests_need ON requests(id_bisogno, data_richiesta);
        CREATE INDEX IF NOT EXISTS idx_requests_fac ON requests(id_struttura);
        CREATE INDEX IF NOT EXISTS idx_ne_date ON need_events(id_bisogno, data_evento DESC, registrato_il DESC);
        CREATE INDEX IF NOT EXISTS idx_re_date ON request_events(id_richiesta, data_evento DESC, registrato_il DESC);
        CREATE INDEX IF NOT EXISTS idx_pe_date ON path_events(id_percorso, data_evento DESC, registrato_il DESC);
        CREATE INDEX IF NOT EXISTS idx_le_date ON location_events(id_paziente, data_evento DESC, registrato_il DESC);
        CREATE INDEX IF NOT EXISTS idx_rev_date ON reviews(id_bisogno, data_evento DESC, registrato_il DESC);
        """)
        for table in ["path_events", "need_events", "request_events", "location_events", "reviews"]:
            con.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_update BEFORE UPDATE ON {table}
                        BEGIN SELECT RAISE(ABORT, 'Evento immutabile; registrare nuova versione'); END""")
            con.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_delete BEFORE DELETE ON {table}
                        BEGIN SELECT RAISE(ABORT, 'Evento immutabile; vietata cancellazione'); END""")
        con.execute("""CREATE TRIGGER IF NOT EXISTS link_patient_match BEFORE INSERT ON path_need_links BEGIN
            SELECT CASE WHEN (SELECT id_paziente FROM pathways WHERE id_percorso=NEW.id_percorso)
                     IS NOT (SELECT id_paziente FROM needs WHERE id_bisogno=NEW.id_bisogno)
                   THEN RAISE(ABORT,'Percorso e bisogno appartengono a pazienti diversi') END;
        END""")


def fetch_all(label: str) -> list[dict]:
    table = TABLE_SQL[label]
    key = TABLE_KEYS[label]
    with connect() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY {key}")]


def insert_record(label: str, **fields) -> str:
    """Insert-only. IDs can be caller supplied (e.g. importing legacy) or generated."""
    if label not in TABLE_COLUMNS:
        raise ValueError(f"Tabella sconosciuta: {label}")
    cols = TABLE_COLUMNS[label]
    record = {k: str(fields.get(k, '') or '') for k in cols}
    record[cols[0]] = record[cols[0]] or new_id({
        "PAZIENTI":"PZ", "STRUTTURE":"ST", "PERCORSI":"PC", "BISOGNI":"BI",
        "PERCORSI_BISOGNI":"LINK", "RICHIESTE":"RIC",
    }.get(label, "EV"))
    if label in EVENT_TABLES and not record["registrato_il"]:
        record["registrato_il"] = now_utc()
    if label == "RICHIESTE" and not record["stato_iniziale"]:
        record["stato_iniziale"] = "INVIATA"
    for required in REQUIRED[label]:
        if not record[required].strip():
            raise ValueError(f"{label}: campo obbligatorio {required}")
    for fld in DATE_FIELDS & set(cols):
        record[fld] = iso(record[fld])
    if label == "PERCORSI" and record['stato_iniziale'] not in PATH_STATES:
        raise ValueError('Stato percorso non valido')
    if label == "BISOGNI" and record['stato_iniziale'] not in NEED_STATES:
        raise ValueError('Stato bisogno non valido')
    if label == "EVENTI_PERCORSO" and record['stato'] not in PATH_STATES:
        raise ValueError('Stato percorso non valido')
    if label == "EVENTI_BISOGNO":
        if record['tipo_evento'] not in NEED_EVENT_KINDS:
            raise ValueError('Tipo evento bisogno non valido')
        if record['tipo_evento']=='STATO' and record['valore'] not in NEED_STATES:
            raise ValueError('Stato bisogno non valido')
        if record['tipo_evento']=='DIMISSIBILITA' and record['valore']:
            record['valore'] = iso(record['valore'])
    if label == "RICHIESTE" and record['stato_iniziale'] not in REQ_STATES:
        raise ValueError('Stato iniziale richiesta non valido')
    if label == "RICHIESTE" and record['stato_iniziale'] == "ACCETTATA":
        raise ValueError('Creare la richiesta come INVIATA e registrare ACCETTATA come evento: chiude atomicamente le altre richieste attive.')
    if label == "EVENTI_RICHIESTA" and record['stato'] not in REQ_STATES:
        raise ValueError('Stato richiesta non valido')
    if label == "COLLOCAZIONI" and record['stato'] not in ('PRESENTE','USCITO','NON_VERIFICATA'):
        raise ValueError('Stato collocazione non valido')
    if label == "VERIFICHE" and record['esito'] not in REVIEW_RESULTS:
        raise ValueError('Esito verifica non valido')
    if label == 'EVENTI_RICHIESTA':
        return register_request_event(
            record['id_richiesta'], record['data_evento'], record['stato'],
            record['canali'], record['note'], record['operatore'],
            event_id=record['id_evento'], recorded_at=record['registrato_il'],
        )['id_evento']
    with connect() as con:
        if label=='RICHIESTE':
            con.execute('BEGIN IMMEDIATE')
            active=_latest_request_states(con,record['id_bisogno'],date.today().isoformat())
            if any(x['state']=='ACCETTATA' for x in active):
                raise ValueError('Esiste già una struttura ACCETTATA per questo bisogno. Non aggiungere una richiesta concorrente prima di una rettifica.')
        placeholders = ','.join('?' for _ in cols)
        con.execute(f"INSERT INTO {TABLE_SQL[label]} ({','.join(cols)}) VALUES ({placeholders})",
                    [record[c] for c in cols])
    return record[cols[0]]

REQUIRED = {
    'PAZIENTI': ('id_paziente','cognome','nome'),
    'STRUTTURE': ('id_struttura','denominazione'),
    'PERCORSI': ('id_percorso','id_paziente','data_attivazione','provenienza','stato_iniziale'),
    'BISOGNI': ('id_bisogno','id_paziente','setting_iniziale','data_inizio','stato_iniziale'),
    'PERCORSI_BISOGNI': ('id_collegamento','id_percorso','id_bisogno','data_collegamento','operatore'),
    'RICHIESTE': ('id_richiesta','id_bisogno','id_struttura','data_richiesta','operatore'),
    'EVENTI_PERCORSO': ('id_evento','id_percorso','data_evento','stato','operatore','registrato_il'),
    'EVENTI_BISOGNO': ('id_evento','id_bisogno','data_evento','tipo_evento','operatore','registrato_il'),
    'EVENTI_RICHIESTA': ('id_evento','id_richiesta','data_evento','stato','operatore','registrato_il'),
    'COLLOCAZIONI': ('id_evento','id_paziente','data_evento','stato','operatore','registrato_il'),
    'VERIFICHE': ('id_verifica','id_bisogno','data_evento','esito','fonte','operatore','registrato_il'),
}
DATE_FIELDS = {'data_nascita','data_attivazione','data_ricovero','data_inizio','data_collegamento','data_richiesta','data_evento'}



def _latest_request_states(con, need_id: str, at: str) -> list[dict]:
    """Effective states for requests already created by the clinical date, within this need."""
    rows=con.execute("""
        SELECT r.id_richiesta, r.id_struttura, f.denominazione, r.data_richiesta,
          COALESCE((SELECT e.stato FROM request_events e
                    WHERE e.id_richiesta=r.id_richiesta AND e.data_evento<=?
                    ORDER BY e.data_evento DESC,e.registrato_il DESC,e.id_evento DESC LIMIT 1), r.stato_iniziale) AS state,
          COALESCE((SELECT e.canali FROM request_events e
                    WHERE e.id_richiesta=r.id_richiesta AND e.data_evento<=? AND e.canali<>''
                    ORDER BY e.data_evento DESC,e.registrato_il DESC,e.id_evento DESC LIMIT 1),r.canali_iniziali) AS channels
        FROM requests r JOIN facilities f ON f.id_struttura=r.id_struttura
        WHERE r.id_bisogno=? AND r.data_richiesta<=?
        ORDER BY r.id_richiesta
    """,(at,at,need_id,at)).fetchall()
    return [dict(r) for r in rows]


def preview_acceptance_closures(request_id: str, event_date) -> list[dict]:
    """Current preview: active sibling requests (the transaction recalculates this list)."""
    at=iso(event_date)
    with connect() as con:
        target=con.execute('SELECT id_bisogno,data_richiesta FROM requests WHERE id_richiesta=?',(request_id,)).fetchone()
        if target is None:raise ValueError('Richiesta inesistente')
        if at<target['data_richiesta']:raise ValueError('Accettazione precedente alla data richiesta')
        return [r for r in _latest_request_states(con,target['id_bisogno'],at)
                if r['id_richiesta']!=request_id and r['state'] in ACTIVE_REQ_STATES]


def _check_acceptance_temporal_order(con, need_id: str, at: str) -> None:
    """Prevent historical acceptance from silently contradicting newer recorded events."""
    newer=con.execute('''SELECT COUNT(*) FROM request_events e
        JOIN requests r ON r.id_richiesta=e.id_richiesta
        WHERE r.id_bisogno=? AND e.data_evento>?''',(need_id,at)).fetchone()[0]
    if newer:
        raise ValueError('Accettazione retrodatata rispetto ad eventi successivi di questo bisogno: serve riconciliazione storica, non chiusura automatica.')


def register_request_event(request_id: str, event_date, state: str, channels: str = '',
                           note: str = '', operator: str = '', event_id: str | None = None,
                           recorded_at: str | None = None) -> dict:
    """Append the acceptance + other active request closures in ONE IMMEDIATE transaction.

    Does not close other needs, pathways, or physical waiting. Accepted != admitted.
    State changes on previously closed sibling requests require an explicit new acceptance;
    arbitrary re-opening is blocked while a winner remains accepted.
    """
    at=iso(event_date)
    if state not in REQ_STATES:raise ValueError('Stato della richiesta non valido')
    if state == 'CHIUSA_PER_ALTRA_ACCETTAZIONE':
        raise ValueError('Questa chiusura è riservata al sistema quando viene accettata un’altra struttura.')
    if not operator.strip():raise ValueError('Operatore obbligatorio')
    rid=event_id or new_id('EV')
    now=recorded_at or now_utc()
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        target=con.execute('''SELECT r.id_bisogno,r.data_richiesta,f.denominazione FROM requests r
                                JOIN facilities f USING(id_struttura) WHERE r.id_richiesta=?''',(request_id,)).fetchone()
        if target is None:raise ValueError('Richiesta inesistente')
        if at<target['data_richiesta']:raise ValueError('Data evento precedente alla richiesta')
        if state=='ACCETTATA':
            _check_acceptance_temporal_order(con,target['id_bisogno'],at)
        siblings=_latest_request_states(con,target['id_bisogno'],at)
        if state in ACTIVE_REQ_STATES and state!='ACCETTATA':
            winners=[x for x in siblings if x['id_richiesta']!=request_id and x['state']=='ACCETTATA']
            if winners:
                raise ValueError('Una struttura risulta già ACCETTATA per questo bisogno. Non si possono riattivare richieste concorrenti; registrare una nuova accettazione o rettificare il caso.')
        con.execute('''INSERT INTO request_events
                     (id_evento,id_richiesta,data_evento,stato,canali,note,operatore,registrato_il)
                     VALUES (?,?,?,?,?,?,?,?)''',
                    (rid,request_id,at,state,channels,note,operator.strip(),now))
        closed=[]
        if state=='ACCETTATA':
            for x in siblings:
                if x['id_richiesta']==request_id or x['state'] not in ACTIVE_REQ_STATES:
                    continue
                con.execute('''INSERT INTO request_events
                        (id_evento,id_richiesta,data_evento,stato,canali,note,operatore,registrato_il)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (new_id('EV'),x['id_richiesta'],at,'CHIUSA_PER_ALTRA_ACCETTAZIONE',x['channels'],
                         f"Chiusura automatica: accettata {target['denominazione']} (richiesta {request_id}); registrata da {operator.strip()}.",
                         'SISTEMA',now))
                closed.append({'id_richiesta':x['id_richiesta'],'struttura':x['denominazione']})
    return {'id_evento':rid,'chiuse':closed}


def reconcile_imported_acceptances(con, need_ids: set[str]) -> int:
    """After all Excel records are inserted, add only MISSING closures, atomically.

    Imported, already-present system closures are respected. Reject inconsistent
    future events rather than silently rewriting them. Caller owns transaction.
    """
    count=0
    for bid in sorted(need_ids):
        acceptances=con.execute('''SELECT e.id_richiesta,e.data_evento,e.registrato_il,e.operatore,
                               f.denominazione,r.data_richiesta
                    FROM request_events e JOIN requests r USING(id_richiesta)
                    JOIN facilities f USING(id_struttura)
                    WHERE r.id_bisogno=? AND e.stato='ACCETTATA'
                    ORDER BY e.data_evento,e.registrato_il,e.id_evento''',(bid,)).fetchall()
        # Ambiguous same-day multi-acceptance requires a deliberate historical correction.
        seen_dates={}
        for a in acceptances:
            if a['data_evento'] in seen_dates and seen_dates[a['data_evento']] != a['id_richiesta']:
                raise ValueError('Import con accettazioni diverse nello stesso giorno per lo stesso bisogno: riconciliare le date.')
            seen_dates[a['data_evento']]=a['id_richiesta']
        for a in acceptances:
            at=a['data_evento']
            if at<a['data_richiesta']:
                raise ValueError('Import: accettazione precedente alla richiesta.')
            siblings=_latest_request_states(con,bid,at)
            # If source already contains closure generated by a previous export, leave it unchanged.
            for x in siblings:
                if x['id_richiesta']==a['id_richiesta'] or x['state'] not in ACTIVE_REQ_STATES:
                    continue
                newer=con.execute('''SELECT COUNT(*) FROM request_events
                    WHERE id_richiesta=? AND data_evento>?''',(x['id_richiesta'],at)).fetchone()[0]
                if newer:
                    subsequent=con.execute('''SELECT stato FROM request_events
                        WHERE id_richiesta=? AND data_evento>?
                        ORDER BY data_evento ASC,registrato_il ASC,id_evento ASC''',
                        (x['id_richiesta'],at)).fetchall()
                    if any(ev['stato']!='ACCETTATA' for ev in subsequent):
                        raise ValueError('Import: la chiusura automatica entrerebbe in conflitto con eventi successivi; serve validazione manuale.')
                con.execute('''INSERT INTO request_events
                    (id_evento,id_richiesta,data_evento,stato,canali,note,operatore,registrato_il)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (new_id('EV'),x['id_richiesta'],at,'CHIUSA_PER_ALTRA_ACCETTAZIONE',x['channels'],
                     f"Chiusura automatica dopo import: accettata {a['denominazione']} (richiesta {a['id_richiesta']}).",
                     'SISTEMA',now_utc()))
                count+=1
    return count
def create_need_with_links(patient_id: str, setting: str, date_start, path_ids: list[str], operator: str) -> str:
    """Atomic creation: all selected pathway links are committed together or none."""
    if not patient_id or not setting.strip() or not operator.strip():
        raise ValueError('Paziente, setting e operatore obbligatori')
    bid=new_id('BI')
    start=iso(date_start)
    with connect() as con:
        con.execute('INSERT INTO needs VALUES (?,?,?,?,?,?)',(bid,patient_id,setting.strip(),start,'APERTA',''))
        for pid in dict.fromkeys(path_ids):
            con.execute('INSERT INTO path_need_links VALUES (?,?,?,?,?)',
                        (new_id('LINK'),pid,bid,start,operator.strip()))
    return bid


def create_requests_for_facilities(bid: str, fac_ids: list[str], at, channels: list[str], note: str, operator: str, initial_status: str = "INVIATA") -> list[str]:
    """Atomic multi-facility fan-out. Each target gets its own independent request ID."""
    if not operator.strip() or not fac_ids:
        raise ValueError('Operatore e almeno una struttura obbligatori')
    if not set(channels).issubset(CHANNELS):
        raise ValueError('Canale sconosciuto')
    if initial_status not in REQ_STATES:
        raise ValueError('Stato iniziale non valido')
    at=iso(at)
    ids=[]
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        current=_latest_request_states(con,bid,date.today().isoformat())
        if any(x['state']=='ACCETTATA' for x in current):
            raise ValueError('È già stata accettata una struttura per questo bisogno; non è possibile aggiungere nuove richieste concorrenti.')
        for fid in dict.fromkeys(fac_ids):
            rid=new_id('RIC')
            con.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?,?)',
                        (rid,bid,fid,at,initial_status,'|'.join(channels),note,operator.strip()))
            ids.append(rid)
    return ids


def _dicts(rows):
    return [dict(row) for row in rows]


def get_paths(patient_id: str | None = None) -> list[dict]:
    with connect() as con:
        sql="""SELECT p.*, a.cognome,a.nome FROM pathways p JOIN patients a USING(id_paziente)"""
        par=()
        if patient_id:
            sql += ' WHERE p.id_paziente=?'; par=(patient_id,)
        return _dicts(con.execute(sql+' ORDER BY p.data_attivazione DESC,p.id_percorso', par))


def get_need_links(bid: str | None = None) -> list[dict]:
    with connect() as con:
        where = 'WHERE l.id_bisogno=?' if bid else ''
        return _dicts(con.execute('''SELECT l.*, p.provenienza,p.presidio,p.reparto,p.id_paziente
                                    FROM path_need_links l JOIN pathways p USING(id_percorso)
                                    '''+where+' ORDER BY l.data_collegamento DESC', (bid,) if bid else ()))


def get_request_history(rid: str) -> list[dict]:
    with connect() as con:
        return _dicts(con.execute('SELECT * FROM request_events WHERE id_richiesta=? ORDER BY data_evento,registrato_il,id_evento', (rid,)))


def get_patient_history(patient_id: str) -> list[dict]:
    """Chronological record with source type. No deduplication across legitimate pathways."""
    with connect() as con:
        q='''SELECT data_evento,registrato_il,'Percorso' AS fonte,id_percorso AS entita,
                stato AS azione, note,operatore FROM path_events WHERE id_percorso IN
                  (SELECT id_percorso FROM pathways WHERE id_paziente=?)
             UNION ALL SELECT data_evento,registrato_il,'Bisogno',id_bisogno,
                tipo_evento||': '||valore,note,operatore FROM need_events WHERE id_bisogno IN
                  (SELECT id_bisogno FROM needs WHERE id_paziente=?)
             UNION ALL SELECT e.data_evento,e.registrato_il,'Struttura',e.id_richiesta,
                e.stato,e.note,e.operatore FROM request_events e JOIN requests r ON r.id_richiesta=e.id_richiesta
                JOIN needs n ON n.id_bisogno=r.id_bisogno WHERE n.id_paziente=?
             UNION ALL SELECT data_evento,registrato_il,'Collocazione',id_paziente,
                stato||': '||presidio||' '||reparto||' '||struttura,note,operatore FROM location_events WHERE id_paziente=?
             UNION ALL SELECT data_evento,registrato_il,'Verifica',id_bisogno,
                esito||': '||fonte,note,operatore FROM reviews WHERE id_bisogno IN
                  (SELECT id_bisogno FROM needs WHERE id_paziente=?)
             ORDER BY data_evento DESC, registrato_il DESC'''
        return _dicts(con.execute(q, (patient_id,)*5))


def snapshot_needs(as_of: date | str, known_on: date | str | None = None) -> list[dict]:
    """Valid-time + knowledge-time snapshot. Status/wait/review/location are independent.

    Returns a row per NEED (not per patient); dashboards must count distinct patient IDs.
    Unknown location never inherits an old provenance silently.
    """
    cutoff = iso(as_of)
    known = iso(known_on or date.today())
    with connect() as con:
        rows=con.execute('''
        WITH eligible AS (
           SELECT * FROM need_events WHERE data_evento<=? AND substr(registrato_il,1,10)<=?
        ), ranked AS (
           SELECT *,ROW_NUMBER() OVER(PARTITION BY id_bisogno,tipo_evento
                              ORDER BY data_evento DESC,registrato_il DESC,id_evento DESC) rn
           FROM eligible WHERE tipo_evento IN ('STATO','SETTING','DIMISSIBILITA')
        ), waits AS (
           SELECT *,ROW_NUMBER() OVER(PARTITION BY id_bisogno
                              ORDER BY data_evento DESC,registrato_il DESC,id_evento DESC) rn
           FROM eligible WHERE tipo_evento IN ('ATTESA_INIZIO','ATTESA_FINE')
        ), last_review AS (
           SELECT *,ROW_NUMBER() OVER(PARTITION BY id_bisogno
                              ORDER BY data_evento DESC,registrato_il DESC,id_verifica DESC) rn
           FROM reviews WHERE data_evento<=? AND substr(registrato_il,1,10)<=?
        ), last_location AS (
           SELECT *,ROW_NUMBER() OVER(PARTITION BY id_paziente
                              ORDER BY data_evento DESC,registrato_il DESC,id_evento DESC) rn
           FROM location_events WHERE data_evento<=? AND substr(registrato_il,1,10)<=?
        ), origins AS (
           SELECT l.id_bisogno,
             GROUP_CONCAT(DISTINCT CASE WHEN p.reparto<>'' THEN p.reparto ELSE NULL END) AS reparti_origine,
             GROUP_CONCAT(DISTINCT CASE WHEN p.presidio<>'' THEN p.presidio ELSE NULL END) AS presidi_origine,
             GROUP_CONCAT(DISTINCT l.id_percorso) AS percorsi_collegati
           FROM path_need_links l JOIN pathways p ON p.id_percorso=l.id_percorso
           WHERE l.data_collegamento<=? AND p.data_attivazione<=?
           GROUP BY l.id_bisogno
        )
        SELECT n.*,p.cognome,p.nome,
               COALESCE(st.valore,n.stato_iniziale) AS stato,
               COALESCE(se.valore,n.setting_iniziale) AS setting_corrente,
               di.valore AS dimissibilita,
               CASE WHEN w.tipo_evento='ATTESA_INIZIO' THEN w.data_evento END AS attesa_dal,
               w.tipo_evento AS ultimo_evento_attesa,
               COALESCE(rv.esito,'DA_VERIFICARE') AS verifica,
               COALESCE(rv.fonte,'') AS fonte_verifica,
               COALESCE(o.reparti_origine,'') AS reparti_origine,
               COALESCE(o.presidi_origine,'') AS presidi_origine,
               COALESCE(o.percorsi_collegati,'') AS percorsi_collegati,
               CASE WHEN lo.stato='PRESENTE' THEN COALESCE(lo.presidio,'') ELSE '' END AS sede_attuale,
               CASE WHEN lo.stato='PRESENTE' THEN COALESCE(lo.reparto,'') ELSE '' END AS reparto_attuale,
               CASE WHEN lo.stato='PRESENTE' THEN COALESCE(lo.struttura,'') ELSE '' END AS struttura_attuale,
               lo.stato AS stato_collocazione,
               lo.data_evento AS collocazione_verificata_il
        FROM needs n JOIN patients p ON p.id_paziente=n.id_paziente
        LEFT JOIN ranked st ON st.id_bisogno=n.id_bisogno AND st.tipo_evento='STATO' AND st.rn=1
        LEFT JOIN ranked se ON se.id_bisogno=n.id_bisogno AND se.tipo_evento='SETTING' AND se.rn=1
        LEFT JOIN ranked di ON di.id_bisogno=n.id_bisogno AND di.tipo_evento='DIMISSIBILITA' AND di.rn=1
        LEFT JOIN waits w ON w.id_bisogno=n.id_bisogno AND w.rn=1
        LEFT JOIN last_review rv ON rv.id_bisogno=n.id_bisogno AND rv.rn=1
        LEFT JOIN last_location lo ON lo.id_paziente=n.id_paziente AND lo.rn=1
        LEFT JOIN origins o ON o.id_bisogno=n.id_bisogno
        WHERE n.data_inizio<=?
        ORDER BY n.data_inizio DESC,n.id_bisogno
        ''',(cutoff,known,cutoff,known,cutoff,known,cutoff,cutoff,cutoff)).fetchall()
    output=[]
    for row in rows:
        item=dict(row)
        # This is a conservative operational stock, not an externally validated clinical prevalence.
        open_need=item['stato'] not in ('CONCLUSA','ANNULLATA','SOSPESA')
        not_excluded=item['verifica']!='NON_IN_ATTESA'
        explicitly_waiting=item['attesa_dal'] is not None
        confirmed=item['verifica']=='ATTESA_CONFERMATA'
        item['attesa_attiva']= bool(open_need and not_excluded and (explicitly_waiting or confirmed))
        item['giorni_attesa']= (date.fromisoformat(cutoff)-date.fromisoformat(item['attesa_dal'])).days if item['attesa_attiva'] and item['attesa_dal'] else None
        item['sede_verificata']= bool(item['stato_collocazione']=='PRESENTE')
        output.append(item)
    return output


def snapshot_requests(as_of: date | str, known_on: date | str | None = None) -> list[dict]:
    cutoff,known=iso(as_of),iso(known_on or date.today())
    needs={n['id_bisogno']:n for n in snapshot_needs(cutoff,known)}
    with connect() as con:
        rows=con.execute('''WITH last AS (
           SELECT *,ROW_NUMBER() OVER(PARTITION BY id_richiesta
                  ORDER BY data_evento DESC,registrato_il DESC,id_evento DESC) rn
           FROM request_events WHERE data_evento<=? AND substr(registrato_il,1,10)<=?
        )
        SELECT r.*,f.denominazione,f.tipologia,f.comune,
           COALESCE(e.stato,r.stato_iniziale) AS stato_richiesta,
           CASE WHEN e.canali IS NOT NULL AND e.canali<>'' THEN e.canali ELSE r.canali_iniziali END AS canali_correnti,
           e.data_evento AS ultimo_aggiornamento
        FROM requests r JOIN facilities f ON f.id_struttura=r.id_struttura
        LEFT JOIN last e ON e.id_richiesta=r.id_richiesta AND e.rn=1
        WHERE r.data_richiesta<=?
        ORDER BY f.denominazione,r.data_richiesta,r.id_richiesta''',(cutoff,known,cutoff)).fetchall()
    result=[]
    for r in rows:
        item=dict(r)
        n=needs.get(item['id_bisogno'])
        if not n:
            continue
        item.update({
            'id_paziente':n['id_paziente'], 'cognome':n['cognome'], 'nome':n['nome'],
            'setting_corrente':n['setting_corrente'], 'reparti_origine':n['reparti_origine'],
            'reparto_attuale':n['reparto_attuale'], 'sede_attuale':n['sede_attuale'],
            'struttura_attuale':n['struttura_attuale'], 'attesa_attiva':n['attesa_attiva'],
            'giorni_attesa':n['giorni_attesa'], 'stato_bisogno':n['stato'],
            'verifica':n['verifica'], 'percorsi_collegati':n['percorsi_collegati'],
        })
        result.append(item)
    return result


def snapshot_paths(as_of: date | str, known_on: date | str | None = None) -> list[dict]:
    cutoff,known=iso(as_of),iso(known_on or date.today())
    with connect() as con:
        rows=con.execute('''WITH last AS (
            SELECT *,ROW_NUMBER() OVER(PARTITION BY id_percorso
                    ORDER BY data_evento DESC,registrato_il DESC,id_evento DESC) rn
            FROM path_events WHERE data_evento<=? AND substr(registrato_il,1,10)<=?
        ) SELECT p.*,COALESCE(e.stato,p.stato_iniziale) stato,
                 a.cognome,a.nome FROM pathways p
          JOIN patients a ON a.id_paziente=p.id_paziente
          LEFT JOIN last e ON e.id_percorso=p.id_percorso AND e.rn=1
          WHERE p.data_attivazione<=? ORDER BY p.data_attivazione DESC''', (cutoff,known,cutoff)).fetchall()
    return _dicts(rows)


def summary(as_of: date | str, known_on: date | str | None = None) -> dict:
    needs=snapshot_needs(as_of,known_on)
    paths=snapshot_paths(as_of,known_on)
    reqs=snapshot_requests(as_of,known_on)
    waiting=[n for n in needs if n['attesa_attiva']]
    return {
        'pazienti_distinti_in_attesa':len({n['id_paziente'] for n in waiting}),
        'bisogni_in_attesa':len(waiting),
        'percorsi_open':sum(p['stato']=='OPEN' for p in paths),
        'richieste_attive':sum(r['stato_richiesta'] not in TERMINAL_REQ_STATES and r['stato_bisogno'] not in ('CONCLUSA','ANNULLATA') for r in reqs),
        'accettate_senza_ingresso':sum(r['stato_richiesta']=='ACCETTATA' for r in reqs),
        'attese_oltre_14_gg':len({n['id_paziente'] for n in waiting if n['giorni_attesa'] is not None and n['giorni_attesa']>14}),
        'giorni_non_calcolabili':len([n for n in waiting if n['giorni_attesa'] is None]),
    }


def quality_alerts(as_of: date | str, known_on: date | str | None = None) -> list[dict]:
    """Only evidence-based warnings. Multiple OPEN paths or targets are legitimate and NOT flagged."""
    needs=snapshot_needs(as_of,known_on)
    reqs=snapshot_requests(as_of,known_on)
    out=[]
    for n in needs:
        if n['attesa_attiva'] and not n['sede_verificata']:
            out.append({'id_paziente':n['id_paziente'],'id_bisogno':n['id_bisogno'], 'controllo':'Sede fisica attuale non verificata'})
        if n['attesa_attiva'] and n['giorni_attesa'] is None:
            out.append({'id_paziente':n['id_paziente'],'id_bisogno':n['id_bisogno'], 'controllo':'Attesa confermata senza data inizio attendibile'})
        if n['dimissibilita'] and n['dimissibilita']<n['data_inizio']:
            out.append({'id_paziente':n['id_paziente'],'id_bisogno':n['id_bisogno'],'controllo':'Dimissibilità anteriore alla data inizio bisogno'})
        if n['verifica']=='NON_IN_ATTESA' and n['attesa_dal']:
            out.append({'id_paziente':n['id_paziente'],'id_bisogno':n['id_bisogno'], 'controllo':'Verifica di non attesa ma evento attesa ancora attivo'})
    for r in reqs:
        if r['stato_richiesta']=='INGRESSO_CONFERMATO' and r['attesa_attiva']:
            out.append({'id_paziente':r['id_paziente'],'id_bisogno':r['id_bisogno'],'controllo':f"Ingresso documentato ma bisogno in attesa: {r['denominazione']}"})
        if r['stato_richiesta']=='ACCETTATA':
            out.append({'id_paziente':r['id_paziente'],'id_bisogno':r['id_bisogno'],'controllo':f"Accettata, ingresso non confermato: {r['denominazione']}"})
    return out
