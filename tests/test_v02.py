import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import database as db
from demo_data import load_demo
from excel_io import export_workbook, parse_workbook, import_preview_or_commit

class TestCOTV03(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp(prefix='cot-v02-test-')
        self.original=db.DB_PATH
        db.DB_PATH=Path(self.tmp)/'cot.db'
        db.init_db()

    def tearDown(self):
        db.DB_PATH=self.original
        shutil.rmtree(self.tmp,ignore_errors=True)

    def test_multiple_open_paths_multiple_needs_and_targets(self):
        load_demo()
        self.assertEqual(len([p for p in db.snapshot_paths('2026-11-12') if p['id_paziente']=='PZ-DEMO-01' and p['stato']=='OPEN']),2)
        self.assertEqual(len([r for r in db.snapshot_requests('2026-11-12') if r['id_bisogno']=='BI-DEMO-1']),3)
        k=db.summary('2026-11-12')
        self.assertEqual(k['pazienti_distinti_in_attesa'],4)
        self.assertEqual(k['bisogni_in_attesa'],5)
        self.assertEqual(k['percorsi_open'],5)
        self.assertEqual(k['accettate_senza_ingresso'],1)
        alerts=' '.join(x['controllo'] for x in db.quality_alerts('2026-11-12'))
        self.assertNotIn('multipli',alerts)
        self.assertNotIn('Doppio',alerts)

    def test_request_status_independent_and_entry_not_equivalent_acceptance(self):
        load_demo()
        ids={r['id_richiesta']:r for r in db.snapshot_requests('2026-11-12')}
        self.assertEqual(ids['RIC-DEMO-2']['stato_richiesta'],'ACCETTATA')
        self.assertEqual(ids['RIC-DEMO-1']['stato_richiesta'],'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        db.insert_record('EVENTI_RICHIESTA',id_richiesta='RIC-DEMO-2',data_evento='2026-11-01',stato='INGRESSO_CONFERMATO',operatore='TEST')
        ids2={r['id_richiesta']:r for r in db.snapshot_requests('2026-11-12')}
        self.assertEqual(ids2['RIC-DEMO-2']['stato_richiesta'],'INGRESSO_CONFERMATO')
        self.assertEqual(ids2['RIC-DEMO-1']['stato_richiesta'],'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertTrue(next(n for n in db.snapshot_needs('2026-11-12') if n['id_bisogno']=='BI-DEMO-1')['attesa_attiva'])

    def test_odc_does_not_close_need_and_old_origin_not_current_location(self):
        load_demo()
        # Original path closed for entry to OdC; shared needs remain open.
        path=next(p for p in db.snapshot_paths('2026-11-12') if p['id_percorso']=='PC-DEMO-1')
        self.assertEqual(path['stato'],'CLOSED')
        waiting=next(n for n in db.snapshot_needs('2026-11-12') if n['id_bisogno']=='BI-DEMO-1')
        self.assertTrue(waiting['attesa_attiva'])
        self.assertEqual(waiting['reparto_attuale'],'OdC Soresina')
        self.assertIn('Medicina interna B',waiting['reparti_origine'])

    def test_as_of_clinical_date_and_known_on_date(self):
        load_demo()
        self.assertEqual(next(r for r in db.snapshot_requests('2026-10-09','2026-11-12') if r['id_richiesta']=='RIC-DEMO-2')['stato_richiesta'],'INVIATA')
        self.assertEqual(next(r for r in db.snapshot_requests('2026-10-11',date.today()) if r['id_richiesta']=='RIC-DEMO-2')['stato_richiesta'],'ACCETTATA')
        self.assertEqual(next(r for r in db.snapshot_requests('2026-10-11','2026-11-11') if r['id_richiesta']=='RIC-DEMO-2')['stato_richiesta'],'INVIATA')
        self.assertIsNone(next(n for n in db.snapshot_needs('2026-10-04','2026-11-12') if n['id_bisogno']=='BI-DEMO-1')['attesa_dal'])

    def test_links_reject_cross_patient_and_duplicates(self):
        load_demo()
        with self.assertRaises(sqlite3.IntegrityError):
            db.insert_record('PERCORSI_BISOGNI',id_percorso='PC-DEMO-3',id_bisogno='BI-DEMO-1',data_collegamento='2026-10-23',operatore='TEST')
        with self.assertRaises(sqlite3.IntegrityError):
            db.insert_record('PERCORSI_BISOGNI',id_percorso='PC-DEMO-2',id_bisogno='BI-DEMO-1',data_collegamento='2026-10-23',operatore='TEST')

    def test_bulk_multiple_targets_atomic(self):
        load_demo()
        before=len(db.fetch_all('RICHIESTE'))
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_requests_for_facilities('BI-DEMO-2',['S-DEMO-1','NON-ESISTE'],'2026-11-01',['Attribuzione'],'','TEST')
        self.assertEqual(len(db.fetch_all('RICHIESTE')),before)
        ids=db.create_requests_for_facilities('BI-DEMO-2',['S-DEMO-1','S-DEMO-2','S-DEMO-2'],'2026-11-01',['Attribuzione','Attenzionamento'],'','TEST')
        self.assertEqual(len(ids),2)
        self.assertTrue(all(r['stato_richiesta']=='INVIATA' for r in db.snapshot_requests('2026-11-12') if r['id_richiesta'] in ids))

    def test_event_immutability(self):
        load_demo()
        with db.connect() as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE need_events SET note='manipolato'")
        with db.connect() as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM need_events")

    def test_excel_roundtrip_idempotent_and_conflict_atomic(self):
        load_demo()
        content=export_workbook()
        parsed=parse_workbook(content)
        report=import_preview_or_commit(parsed,commit=True)
        self.assertEqual(sum(x['nuove'] for x in report.values()),0)
        self.assertGreater(sum(x['gia_presenti'] for x in report.values()),0)
        # One fresh patient followed by conflict in a later table, entire transaction rolls back.
        parsed['PAZIENTI'].append({'id_paziente':'TEMP','cognome':'ANON','nome':'TEST','codice_fiscale':'','data_nascita':''})
        parsed['STRUTTURE'][0]['denominazione']='Alterata'
        with self.assertRaises(ValueError):
            import_preview_or_commit(parsed,commit=True)
        self.assertFalse(any(p['id_paziente']=='TEMP' for p in db.fetch_all('PAZIENTI')))

    def test_excel_supplied_example_import_preserves_timestamps(self):
        source=Path(__file__).resolve().parent.parent/'COT_esempio_sintetico_v0_2.xlsx'
        parsed=parse_workbook(source.read_bytes())
        self.assertTrue(parsed['EVENTI_BISOGNO'][0]['registrato_il'].startswith('2026-11-12'))
        first=import_preview_or_commit(parsed,commit=True)
        self.assertEqual(sum(x['nuove'] for x in first.values()),52)
        k=db.summary('2026-11-12')
        self.assertEqual(k['pazienti_distinti_in_attesa'],4)
        self.assertEqual(k['percorsi_open'],5)
        self.assertEqual(k['accettate_senza_ingresso'],1)

    def test_empty_excel_template_schema_and_review_override(self):
        load_demo()
        db.insert_record('VERIFICHE',id_bisogno='BI-DEMO-1',data_evento='2026-11-11',esito='NON_IN_ATTESA',fonte='Verifica sul campo',operatore='TEST')
        n=next(n for n in db.snapshot_needs('2026-11-12') if n['id_bisogno']=='BI-DEMO-1')
        self.assertFalse(n['attesa_attiva'])
        self.assertTrue(any('Verifica di non attesa' in x['controllo'] for x in db.quality_alerts('2026-11-12')))

if __name__=='__main__': unittest.main()
