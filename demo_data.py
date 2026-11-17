"""Load one explicit synthetic demonstration, only when database is empty."""
import database as db


def load_demo():
    if db.fetch_all('PAZIENTI'):
        raise ValueError('Database non vuoto: la demo non viene caricata per evitare contaminazioni.')
    # Fixed dates are deliberately before the 2026-11-12 reference demo.
    patients=[('PZ-DEMO-01','ROSSI','Ada'),('PZ-DEMO-02','BIANCHI','Luca'),('PZ-DEMO-03','VERDI','Elena'),('PZ-DEMO-04','NERI','Paolo')]
    for pid,surname,name in patients:
        db.insert_record('PAZIENTI',id_paziente=pid,cognome=surname,nome=name)
    for sid,name in [('S-DEMO-1','Cremona Solidale'),('S-DEMO-2','Fondazione Sospiro'),('S-DEMO-3','Ancelle della Carità'),('S-DEMO-4','OdC di Soresina')]:
        db.insert_record('STRUTTURE',id_struttura=sid,denominazione=name,tipologia='Struttura dimissione')
    for x,pid,ward in [(1,'PZ-DEMO-01','Medicina interna B'),(2,'PZ-DEMO-01','OdC Soresina'),(3,'PZ-DEMO-02','Neurologia'),(4,'PZ-DEMO-03','Pneumologia'),(5,'PZ-DEMO-04','Medicina interna A'),(6,'PZ-DEMO-01','OdC Cremona')]:
        db.insert_record('PERCORSI',id_percorso=f'PC-DEMO-{x}',id_paziente=pid,data_attivazione='2026-10-01',provenienza='Ospedale',presidio='Cremona' if x!=2 else 'Soresina',reparto=ward,stato_iniziale='OPEN')
    # Same patient: two OPEN pathways and two independent concurrent needs.
    specs=[('BI-DEMO-1','PZ-DEMO-01','Riabilitazione 56',['PC-DEMO-1','PC-DEMO-2','PC-DEMO-6']),
           ('BI-DEMO-2','PZ-DEMO-01','Lungodegenza 60',['PC-DEMO-1','PC-DEMO-2','PC-DEMO-6']),
           ('BI-DEMO-3','PZ-DEMO-02','Riabilitazione 56',['PC-DEMO-3']),
           ('BI-DEMO-4','PZ-DEMO-03','Subacuti',['PC-DEMO-4']),
           ('BI-DEMO-5','PZ-DEMO-04','Lungodegenza 60',['PC-DEMO-5'])]
    for bid,pid,setting,links in specs:
        db.insert_record('BISOGNI',id_bisogno=bid,id_paziente=pid,setting_iniziale=setting,data_inizio='2026-10-01',stato_iniziale='APERTA')
        for i,p in enumerate(links):
            db.insert_record('PERCORSI_BISOGNI',id_collegamento=f'LINK-{bid}-{i}',id_percorso=p,id_bisogno=bid,data_collegamento='2026-10-01' if i==0 else '2026-10-20',operatore='DEMO')
        db.insert_record('EVENTI_BISOGNO',id_bisogno=bid,data_evento='2026-10-05',tipo_evento='ATTESA_INIZIO',operatore='DEMO')
    dest=[('BI-DEMO-1','S-DEMO-1','ATTENZIONATA'),('BI-DEMO-1','S-DEMO-2','ACCETTATA'),
          ('BI-DEMO-1','S-DEMO-3','IN_ATTESA_RISPOSTA'),('BI-DEMO-2','S-DEMO-1','ATTRIBUITA'),
          ('BI-DEMO-3','S-DEMO-2','RIFIUTATA'),('BI-DEMO-4','S-DEMO-3','INGRESSO_CONFERMATO'),
          ('BI-DEMO-5','S-DEMO-1','INVIATA')]
    for i,(bid,sid,state) in enumerate(dest,1):
        db.insert_record('RICHIESTE',id_richiesta=f'RIC-DEMO-{i}',id_bisogno=bid,id_struttura=sid,data_richiesta='2026-10-08',canali_iniziali='Attribuzione|Attenzionamento',operatore='DEMO')
    # Accepted event comes after other same-need request statuses: two active competitors close.
    for i,(bid,sid,state) in enumerate(dest,1):
        if state=='ACCETTATA':continue
        db.insert_record('EVENTI_RICHIESTA',id_richiesta=f'RIC-DEMO-{i}',data_evento='2026-10-10',stato=state,canali='Attribuzione|Attenzionamento',operatore='DEMO')
    db.register_request_event('RIC-DEMO-2','2026-10-10','ACCETTATA','Attribuzione|Attenzionamento',operator='DEMO')
    db.insert_record('COLLOCAZIONI',id_paziente='PZ-DEMO-01',data_evento='2026-10-20',presidio='Soresina',reparto='OdC Soresina',stato='PRESENTE',operatore='DEMO')
    db.insert_record('EVENTI_PERCORSO',id_percorso='PC-DEMO-1',data_evento='2026-10-20',stato='CLOSED',note='Ingresso OdC, attesa esterna continua',operatore='DEMO')
    db.insert_record('VERIFICHE',id_bisogno='BI-DEMO-1',data_evento='2026-10-22',esito='ATTESA_CONFERMATA',fonte='Operatore demo',operatore='DEMO')
    return True
