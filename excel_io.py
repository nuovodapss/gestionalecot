"""COT v0.3 Excel exchange - strict, atomic, idempotent, NEVER a live shared database.

The exported workbook can be ingested again. Existing IDs with changed payloads are
rejected rather than silently overwritten; longitudinal changes are new event rows.
Not a converter for R7 encrypted JSON files.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import math

import pandas as pd

import database as db

MAX_BYTES=25*1024*1024
MAX_ROWS=100_000


def _normalize(value, column):
    if value is None or (not isinstance(value, (list,dict)) and pd.isna(value)):
        return ''
    if isinstance(value, (datetime,date,pd.Timestamp)):
        return value.strftime('%Y-%m-%d') if column in db.DATE_FIELDS else value.isoformat()
    # Excel may convert ISO timestamps/dates into serial numeric values.
    if isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(float(value)):
        if column in db.DATE_FIELDS or column == 'registrato_il':
            if 1 <= float(value) <= 100000:
                converted=datetime(1899,12,30,tzinfo=timezone.utc)+timedelta(days=float(value))
                return converted.date().isoformat() if column in db.DATE_FIELDS else converted.isoformat(timespec='microseconds')
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        value=str(int(value))
    res=str(value).strip()
    if column in db.DATE_FIELDS and res:
        return db.iso(res)
    return res


def _validate(parsed):
    """Check all foreign keys using existing and incoming rows, without requiring one path per patient."""
    keys = {t:{r[db.TABLE_KEYS[t]] for r in db.fetch_all(t)} |
            {r[db.TABLE_KEYS[t]] for r in parsed[t]} for t in db.TABLE_COLUMNS}
    rels = {
        'PERCORSI': [('id_paziente','PAZIENTI','id_paziente')],
        'BISOGNI': [('id_paziente','PAZIENTI','id_paziente')],
        'PERCORSI_BISOGNI': [('id_percorso','PERCORSI','id_percorso'),('id_bisogno','BISOGNI','id_bisogno')],
        'RICHIESTE': [('id_bisogno','BISOGNI','id_bisogno'),('id_struttura','STRUTTURE','id_struttura')],
        'EVENTI_PERCORSO': [('id_percorso','PERCORSI','id_percorso')],
        'EVENTI_BISOGNO': [('id_bisogno','BISOGNI','id_bisogno')],
        'EVENTI_RICHIESTA': [('id_richiesta','RICHIESTE','id_richiesta')],
        'COLLOCAZIONI': [('id_paziente','PAZIENTI','id_paziente')],
        'VERIFICHE': [('id_bisogno','BISOGNI','id_bisogno')],
    }
    for label,refs in rels.items():
        for row in parsed[label]:
            for field,parent,_ in refs:
                if row[field] not in keys[parent]:
                    raise ValueError(f'{label}: {field}={row[field]} non esiste in {parent}')
    paths={r['id_percorso']:r['id_paziente'] for r in db.fetch_all('PERCORSI')}
    paths.update({r['id_percorso']:r['id_paziente'] for r in parsed['PERCORSI']})
    needs={r['id_bisogno']:r['id_paziente'] for r in db.fetch_all('BISOGNI')}
    needs.update({r['id_bisogno']:r['id_paziente'] for r in parsed['BISOGNI']})
    for r in parsed['PERCORSI_BISOGNI']:
        if paths[r['id_percorso']] != needs[r['id_bisogno']]:
            raise ValueError('PERCORSI_BISOGNI: collegamento fra pazienti differenti')
    # Guard minimum quality; same patient legitimately may have 2+ OPEN pathways / many requests.
    for row in parsed['RICHIESTE']:
        if row['stato_iniziale']=='ACCETTATA':
            raise ValueError('RICHIESTE: registrare ACCETTATA come evento in EVENTI_RICHIESTA, non come stato_iniziale.')
    for label, vals, field in (
        ('PERCORSI',db.PATH_STATES,'stato_iniziale'),
        ('RICHIESTE',db.REQ_STATES,'stato_iniziale'),
        ('BISOGNI',db.NEED_STATES,'stato_iniziale'),
        ('EVENTI_PERCORSO',db.PATH_STATES,'stato'),
        ('EVENTI_BISOGNO',db.NEED_EVENT_KINDS,'tipo_evento'),
        ('EVENTI_RICHIESTA',db.REQ_STATES,'stato'),
        ('VERIFICHE',db.REVIEW_RESULTS,'esito'),
    ):
        for r in parsed[label]:
            if r[field] not in vals:
                raise ValueError(f'{label}: valore {r[field]!r} non ammesso in {field}')
    for r in parsed['EVENTI_BISOGNO']:
        if r['tipo_evento']=='STATO' and r['valore'] not in db.NEED_STATES:
            raise ValueError('EVENTI_BISOGNO: stato non valido')
        if r['tipo_evento']=='DIMISSIBILITA' and r['valore']:
            db.iso(r['valore'])
    for r in parsed['COLLOCAZIONI']:
        if r['stato'] not in ('PRESENTE','USCITO','NON_VERIFICATA'):
            raise ValueError('COLLOCAZIONI: stato non valido')


def parse_workbook(content: bytes):
    if len(content)>MAX_BYTES:
        raise ValueError('File Excel oltre 25 MB: importazione non consentita nel prototipo.')
    xls=pd.ExcelFile(BytesIO(content),engine='openpyxl')
    missing=set(db.TABLE_COLUMNS)-set(xls.sheet_names)
    if missing:
        raise ValueError('Fogli mancanti: '+', '.join(sorted(missing)))
    parsed={}; n=0
    for label,cols in db.TABLE_COLUMNS.items():
        frame=pd.read_excel(xls,sheet_name=label,dtype=object)
        missing_cols=set(cols)-set(frame.columns)
        if missing_cols:
            raise ValueError(f'{label}: colonne mancanti: {sorted(missing_cols)}')
        n+=len(frame)
        if n>MAX_ROWS:
            raise ValueError('Troppi record (massimo 100.000 righe per importazione).')
        seen=set(); rows=[]
        for i,items in enumerate(frame[cols].to_dict('records'),start=2):
            r={c:_normalize(items[c],c) for c in cols}
            if not any(r.values()): continue
            for field in db.REQUIRED[label]:
                if not r[field]:
                    raise ValueError(f'{label} riga {i}: campo obbligatorio {field} mancante')
            if r[cols[0]] in seen:
                raise ValueError(f'{label} riga {i}: ID ripetuto nel file: {r[cols[0]]}')
            seen.add(r[cols[0]])
            rows.append(r)
        parsed[label]=rows
    _validate(parsed)
    return parsed


def import_preview_or_commit(parsed, commit=False):
    """One SQLite transaction, including preview. Conflicting IDs reject ALL records."""
    stats={}
    with db.connect() as con:
        if commit: con.execute('BEGIN IMMEDIATE')
        affected_needs=set()
        for label in db.IMPORT_ORDER:
            cols=db.TABLE_COLUMNS[label]
            table=db.TABLE_SQL[label]
            key=cols[0]
            cnt={'nuove':0,'gia_presenti':0}
            for r in parsed[label]:
                old=con.execute(f'SELECT * FROM {table} WHERE {key}=?',(r[key],)).fetchone()
                if old:
                    if any(str(old[c] if old[c] is not None else '')!=r[c] for c in cols):
                        raise ValueError(f'CONFLITTO {label} {r[key]}: record differente già presente; annullata intera importazione')
                    cnt['gia_presenti']+=1
                else:
                    cnt['nuove']+=1
                    if commit:
                        if label=='RICHIESTE':
                            affected_needs.add(r['id_bisogno'])
                        if label=='EVENTI_RICHIESTA' and r['stato']=='ACCETTATA':
                            need_id=con.execute('SELECT id_bisogno FROM requests WHERE id_richiesta=?',(r['id_richiesta'],)).fetchone()[0]
                            affected_needs.add(need_id)
                        ph=','.join('?' for _ in cols)
                        con.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({ph})', [r[c] for c in cols])
            stats[label]=cnt
        if commit and affected_needs:
            stats['CHIUSURE_AUTOMATICHE']={'nuove':db.reconcile_imported_acceptances(con,affected_needs),'gia_presenti':0}
    return stats


def export_workbook() -> bytes:
    buf=BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter', engine_kwargs={'options':{
        'strings_to_formulas':False,'strings_to_urls':False}}) as writer:
        header=writer.book.add_format({'bold':True,'bg_color':'#185B85','font_color':'#FFFFFF','text_wrap':True,'valign':'vcenter'})
        textfmt=writer.book.add_format({'num_format':'@'})
        for label,cols in db.TABLE_COLUMNS.items():
            frame=pd.DataFrame(db.fetch_all(label), columns=cols)
            frame.to_excel(writer,sheet_name=label,index=False)
            ws=writer.sheets[label]
            ws.freeze_panes(1,0)
            ws.set_row(0,30)
            ws.autofilter(0,0,max(1,len(frame)),len(cols)-1)
            for i,c in enumerate(cols):
                ws.write(0,i,c,header)
                ws.set_column(i,i,min(34,max(16,len(c)+4)),textfmt)
        notes=[
            'COT v0.3 - PROTOTIPO per collaudo con dati fittizi o anonimizzati.',
            'Le 11 tabelle contengono chiavi relazionali: NON eliminare o alterare gli ID.',
            'Un paziente può avere più percorsi OPEN; un bisogno può collegarsi a più percorsi.',
            'Prima dell’accettazione, un bisogno può avere più richieste contemporanee a strutture differenti.',
            'ACCETTATA chiude automaticamente le altre richieste attive per lo stesso bisogno; non gli altri bisogni del paziente.',
            'Per attribuzione/attenzionamento multipli: canali separati da |, ad esempio Attribuzione|Attenzionamento.',
            'Le date devono usare ISO 8601, ad esempio 2026-11-12.',
            'Eventi e chiusure vengono storicizzati; importazioni identiche non duplicano i record già presenti.',
            'Non importare JSON cifrati R7 in questo formato: richiedono adattatore verificato.',
            'Questo Excel è in CHIARO: non caricare dati clinici identificativi prima di approvazione IT/DPO.',
        ]
        pd.DataFrame({'LEGGIMI':notes}).to_excel(writer,sheet_name='LEGGIMI',index=False)
        writer.sheets['LEGGIMI'].set_column('A:A',115)
    return buf.getvalue()
