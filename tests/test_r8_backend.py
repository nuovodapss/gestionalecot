from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import InvalidEnvelope, SqliteEncryptedStore, StorageConflict


def envelope():
    return json.dumps(dict(format='COT_PERCORSI_ENCRYPTED_JSON',archiveVersion=2,
             cipher='AES-GCM-256',kdf='PBKDF2-SHA-256',iterations=250000,
             salt='a'*24,iv='b'*16,ciphertext='c'*50))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SqliteEncryptedStore(Path(self.tmp.name)/'backup.sqlite3')
    def tearDown(self):
        self.tmp.cleanup()

    def test_first_revision(self):
        self.assertEqual(self.store.latest().revision,0)
        got=self.store.put(envelope(),0)
        self.assertEqual(got.revision,1)
        self.assertEqual(self.store.latest().envelope,envelope())

    def test_conflict_is_blocking(self):
        self.store.put(envelope(),0)
        with self.assertRaises(StorageConflict):self.store.put(envelope(),0)
        self.assertEqual(self.store.latest().revision,1)

    def test_concurrent_writes_use_one_revision(self):
        barrier=threading.Barrier(2)
        outcomes=[]
        def write(payload):
            barrier.wait()
            try:outcomes.append(self.store.put(payload,0).revision)
            except StorageConflict:outcomes.append('conflict')
        threads=[threading.Thread(target=write,args=(json.dumps({**json.loads(envelope()),'nonce':i}),)) for i in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertCountEqual(outcomes,[1,'conflict'])
        self.assertEqual(self.store.latest().revision,1)

    def test_history_preserved(self):
        self.store.put(envelope(),0)
        self.store.put(envelope()+' ',1)
        with self.store.connect() as db:
            n=db.execute('SELECT COUNT(*) FROM encrypted_snapshots').fetchone()[0]
        self.assertEqual(n,2)

    def test_invalid_plaintext_rejected(self):
        for bad in ('{}','{"patients":[]}', '{broken',''):
            with self.assertRaises(InvalidEnvelope):self.store.put(bad,0)
        self.assertEqual(self.store.latest().revision,0)

    def test_exact_reference_preserved(self):
        root=Path(__file__).resolve().parents[1]/'frontend'
        original=(root/'R8_ORIGINALE_IMMUTATO.html').read_bytes()
        augmented=(root/'index.html').read_bytes()
        self.assertEqual(augmented.replace(b'<script src="cot_streamlit_bridge.js"></script>\n',b''),original)
        self.assertIn(b"askPassword('open'",original)
        self.assertIn(b"db=await decryptArchive(env,p)",original)
        for screen in (b'Coda COT',b'OdC oggi',b'Lista OdC',b'Hospice',b'Strutture',b'Cruscotto',b'Qualit',b'Dati & backup'):
            self.assertIn(screen, original)

    def test_streamlit_wrapper_embeds_the_r8_component(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/'app.py').read_text()
        self.assertIn("components.declare_component('cot_r8_full_parity', path=str(FRONTEND))",app)
        self.assertIn("FRONTEND = ROOT / 'frontend'",app)
        self.assertIn("layout='wide'",app)
        self.assertIn('from relational_session import import_archive',app)
        self.assertNotIn('SqliteEncryptedStore',app)

    def test_streamlit_bridge_uses_registered_v1_messages_and_frame_lifecycle(self):
        root=Path(__file__).resolve().parents[1]
        bridge=(root/'frontend'/'cot_streamlit_bridge.js').read_text()
        protocol=(root/'streamlit_bridge.py').read_text()
        self.assertIn("type:'streamlit:componentReady',apiVersion:1",bridge)
        self.assertIn("post('streamlit:setComponentValue'",bridge)
        self.assertIn("post('streamlit:setFrameHeight'",bridge)
        self.assertIn("event.source!==window.parent",bridge)
        self.assertIn("event.origin!==window.location.origin",bridge)
        self.assertIn("window.addEventListener('pagehide'",bridge)
        self.assertNotIn('readyAttempts',bridge)
        self.assertNotIn('sendHeight()',bridge)
        self.assertNotIn('serverRevision',bridge)
        self.assertIn('function openRelationalArchive(payload)',bridge)
        self.assertIn("Archivio relazionale non cifrato",bridge)
        self.assertIn("sendValue({kind:'probe_ack'",bridge)
        self.assertIn('function setFrameHeight()',bridge)
        self.assertIn('function openRelationalArchive(payload)',bridge)
        self.assertIn('const nextDb=migrateDb(JSON.parse(JSON.stringify(payload)))',bridge)
        self.assertIn("StreamlitV1.setFrameHeight(Math.max(850",bridge)
        self.assertIn('if kind == "probe":',protocol)
        self.assertIn('if kind == "loaded":',protocol)

    def test_private_local_data_is_ignored_by_git(self):
        root=Path(__file__).resolve().parents[1]
        ignore=(root/'.gitignore').read_text()
        for pattern in ('data/*','*.db','*.sqlite','*.sqlite3','COT_BACKUP_*.json','COT_ARCHIVIO_*.json','.streamlit/secrets.toml'):
            self.assertIn(pattern,ignore)


if __name__=='__main__':unittest.main()
