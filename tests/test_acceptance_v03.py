"""Regression tests of automatic closures after acceptance (synthetic data only)."""
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import database as db
from demo_data import load_demo
from excel_io import export_workbook, parse_workbook, import_preview_or_commit

class AcceptanceAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp(prefix='cot-v03-acceptance-')
        self.original=db.DB_PATH
        db.DB_PATH=Path(self.tmp)/'cot.db'
        db.init_db()
        load_demo()

    def tearDown(self):
        db.DB_PATH=self.original
        shutil.rmtree(self.tmp,ignore_errors=True)

    def state(self,request_id,when=None):
        when=when or date.today()
        return next(r for r in db.snapshot_requests(when) if r['id_richiesta']==request_id)['stato_richiesta']

    def test_accepted_closes_every_other_active_sibling_but_not_other_needs(self):
        self.assertEqual(self.state('RIC-DEMO-2'),'ACCETTATA')
        self.assertEqual(self.state('RIC-DEMO-1'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertEqual(self.state('RIC-DEMO-3'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertEqual(self.state('RIC-DEMO-4'),'ATTRIBUITA')  # independent need, same patient
        self.assertEqual(len([x for x in db.snapshot_paths(date.today()) if x['id_paziente']=='PZ-DEMO-01' and x['stato']=='OPEN']),2)
        closures=[e for e in db.fetch_all('EVENTI_RICHIESTA') if e['stato']=='CHIUSA_PER_ALTRA_ACCETTAZIONE']
        self.assertEqual(len(closures),2)
        self.assertTrue(all(e['operatore']=='SISTEMA' for e in closures))
        self.assertTrue(all('Fondazione Sospiro' in e['note'] for e in closures))
        self.assertEqual(len({e['registrato_il'] for e in closures}),1)
        accepted=next(e for e in db.fetch_all('EVENTI_RICHIESTA') if e['stato']=='ACCETTATA')
        self.assertTrue(all(e['registrato_il']==accepted['registrato_il'] for e in closures))
        self.assertEqual(db.summary(date.today())['richieste_attive'],3)

    def test_previous_history_remains_visible(self):
        self.assertEqual(self.state('RIC-DEMO-1','2026-10-09'),'INVIATA')
        self.assertEqual(self.state('RIC-DEMO-1','2026-10-10'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        h=db.get_request_history('RIC-DEMO-1')
        self.assertEqual([e['stato'] for e in h],['ATTENZIONATA','CHIUSA_PER_ALTRA_ACCETTAZIONE'])

    def test_acceptance_does_not_claim_physical_admission(self):
        self.assertEqual(self.state('RIC-DEMO-2'),'ACCETTATA')
        need=next(n for n in db.snapshot_needs(date.today()) if n['id_bisogno']=='BI-DEMO-1')
        self.assertTrue(need['attesa_attiva'])
        self.assertEqual(need['stato'],'APERTA')
        self.assertNotEqual(self.state('RIC-DEMO-2'),'INGRESSO_CONFERMATO')

    def test_requests_created_after_existing_acceptance_blocked_atomic(self):
        before=len(db.fetch_all('RICHIESTE'))
        with self.assertRaises(ValueError):
            db.create_requests_for_facilities('BI-DEMO-1',['S-DEMO-1','S-DEMO-4'],date.today(),['Attenzionamento'],'','OPERATORE')
        with self.assertRaises(ValueError):
            db.insert_record('RICHIESTE',id_bisogno='BI-DEMO-1',id_struttura='S-DEMO-4',data_richiesta=date.today(),operatore='OPERATORE')
        self.assertEqual(len(db.fetch_all('RICHIESTE')),before)

    def test_second_acceptance_replaces_winner_and_closes_previous_winner(self):
        result=db.register_request_event('RIC-DEMO-1','2026-10-13','ACCETTATA',operator='OPERATORE',note='Nuova accettazione')
        self.assertEqual(len(result['chiuse']),1)
        self.assertEqual(result['chiuse'][0]['id_richiesta'],'RIC-DEMO-2')
        self.assertEqual(self.state('RIC-DEMO-1'),'ACCETTATA')
        self.assertEqual(self.state('RIC-DEMO-2'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertEqual(self.state('RIC-DEMO-3'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertEqual(self.state('RIC-DEMO-4'),'ATTRIBUITA')
        self.assertEqual(self.state('RIC-DEMO-2','2026-10-12'),'ACCETTATA')

    def test_refused_and_previously_transferred_are_not_rewritten(self):
        existing=db.fetch_all('EVENTI_RICHIESTA')
        db.create_requests_for_facilities('BI-DEMO-2',['S-DEMO-2','S-DEMO-3','S-DEMO-4'],'2026-10-12',['Attenzionamento'],'','OPERATORE')
        new=[r for r in db.fetch_all('RICHIESTE') if r['id_bisogno']=='BI-DEMO-2']
        ids={r['id_struttura']:r['id_richiesta'] for r in new}
        db.register_request_event(ids['S-DEMO-2'],'2026-10-13','RIFIUTATA',operator='OPERATORE')
        db.register_request_event(ids['S-DEMO-4'],'2026-10-13','INGRESSO_CONFERMATO',operator='OPERATORE')
        result=db.register_request_event(ids['S-DEMO-3'],'2026-10-14','ACCETTATA',operator='OPERATORE')
        self.assertEqual({r['id_richiesta'] for r in result['chiuse']},{ids['S-DEMO-1']} if 'S-DEMO-1' in ids else {'RIC-DEMO-4'})
        self.assertEqual(self.state(ids['S-DEMO-2']),'RIFIUTATA')
        self.assertEqual(self.state(ids['S-DEMO-4']),'INGRESSO_CONFERMATO')
        self.assertEqual(self.state(ids['S-DEMO-3']),'ACCETTATA')
        self.assertEqual(self.state('RIC-DEMO-4'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')

    def test_closed_competitor_cannot_reopen_while_winner_accepted(self):
        n_before=len(db.get_request_history('RIC-DEMO-1'))
        with self.assertRaises(ValueError):
            db.register_request_event('RIC-DEMO-1','2026-10-12','ATTENZIONATA',operator='OPERATORE')
        self.assertEqual(len(db.get_request_history('RIC-DEMO-1')),n_before)

    def test_acceptance_and_closures_rollback_together_if_any_closure_fails(self):
        # Need BI-DEMO-2: one ACTIVE competitor, no accepted winner.
        db.create_requests_for_facilities('BI-DEMO-2',['S-DEMO-2'],'2026-10-12',['Attenzionamento'],'','OPERATORE')
        rid=next(r['id_richiesta'] for r in db.fetch_all('RICHIESTE') if r['id_bisogno']=='BI-DEMO-2' and r['id_struttura']=='S-DEMO-2')
        with db.connect() as con:
            con.execute('''CREATE TRIGGER fail_closure BEFORE INSERT ON request_events
                WHEN NEW.stato='CHIUSA_PER_ALTRA_ACCETTAZIONE'
                BEGIN SELECT RAISE(ABORT,'collaudo rollback'); END''')
        before=len(db.fetch_all('EVENTI_RICHIESTA'))
        with self.assertRaises(sqlite3.IntegrityError):
            db.register_request_event(rid,'2026-10-14','ACCETTATA',operator='OPERATORE')
        self.assertEqual(len(db.fetch_all('EVENTI_RICHIESTA')),before)
        self.assertEqual(self.state(rid),'INVIATA')
        self.assertEqual(self.state('RIC-DEMO-4'),'ATTRIBUITA')

    def test_import_export_with_auto_closures_does_not_generate_duplicates(self):
        content=export_workbook()
        data=parse_workbook(content)
        db.DB_PATH=Path(self.tmp)/'fresh.db'
        db.init_db()
        first=import_preview_or_commit(data,commit=True)
        self.assertEqual(first.get('CHIUSURE_AUTOMATICHE',{}).get('nuove',0),0)
        n=len(db.fetch_all('EVENTI_RICHIESTA'))
        second=import_preview_or_commit(data,commit=True)
        self.assertEqual(sum(s['nuove'] for s in second.values()),0)
        self.assertEqual(len(db.fetch_all('EVENTI_RICHIESTA')),n)
        self.assertEqual(self.state('RIC-DEMO-2'),'ACCETTATA')
        self.assertEqual(self.state('RIC-DEMO-1'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')

    def test_import_legacy_example_auto_closes_siblings(self):
        source=Path(__file__).resolve().parent.parent/'COT_esempio_sintetico_v0_2.xlsx'
        data=parse_workbook(source.read_bytes())
        db.DB_PATH=Path(self.tmp)/'from_legacy.db'
        db.init_db()
        result=import_preview_or_commit(data,commit=True)
        self.assertEqual(result['CHIUSURE_AUTOMATICHE']['nuove'],2)
        self.assertEqual(self.state('RIC-DEMO-1'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')
        self.assertEqual(self.state('RIC-DEMO-2'),'ACCETTATA')
        self.assertEqual(self.state('RIC-DEMO-3'),'CHIUSA_PER_ALTRA_ACCETTAZIONE')

    def test_backdated_acceptance_does_not_rewrite_later_events(self):
        db.create_requests_for_facilities('BI-DEMO-2',['S-DEMO-2'],'2026-10-12',['Attenzionamento'],'','OPERATORE')
        rid=next(r['id_richiesta'] for r in db.fetch_all('RICHIESTE') if r['id_bisogno']=='BI-DEMO-2' and r['id_struttura']=='S-DEMO-2')
        db.register_request_event(rid,'2026-10-16','IN_ATTESA_RISPOSTA',operator='OPERATORE')
        before=len(db.fetch_all('EVENTI_RICHIESTA'))
        with self.assertRaises(ValueError):
            db.register_request_event('RIC-DEMO-4','2026-10-15','ACCETTATA',operator='OPERATORE')
        self.assertEqual(len(db.fetch_all('EVENTI_RICHIESTA')),before)

if __name__=='__main__': unittest.main()
