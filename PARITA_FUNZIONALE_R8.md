# Matrice di audit e parità R8 → Streamlit

Aggiornata il 17 novembre 2026. La baseline funzionale e grafica è `frontend/R8_ORIGINALE_IMMUTATO.html` (SHA-256 registrato in `frontend/SHA256_R8.txt`). `frontend/index.html` mantiene il contenuto della baseline e aggiunge il bridge Streamlit. Questa equivalenza è verificata da `test_exact_reference_preserved`; non dimostra che l’interfaccia funzioni correttamente nel browser integrato.

Evidenza ciclo 2: Streamlit 1.51.0 è stato avviato con Python 3.12 su `localhost:8501`; Chrome ha mostrato la pagina e l'iframe del componente, con il gate R8 e il pulsante per creare un archivio sintetico. Per scelta dell'utente non è stata impostata una password di prova; non sono state aperte le schermate operative né inseriti dati.

## Schermate e stato di verifica

| Schermata R8 | Funzioni presenti nel sorgente | Stato dell'integrazione Streamlit | Test di parità richiesti |
|---|---|---|---|
| Coda COT | Ricerca globale, filtri percorso/consulenza, lista pazienti, creazione e modifica anagrafica | HTML R8 caricato nell'iframe; schermata operativa **NON VERIFICATA** (gate archivio osservato in Chrome) | Ricerca, filtri, ordinamento, validazioni e persistenza di paziente |
| Scheda paziente | Tab, consulenze, percorsi, collocazione, ricoveri/trasferimenti, cronologia e rettifiche | HTML R8 incorporato; flussi UI **NON VERIFICATI** | Navigazione tab, collegamenti, timeline, aggiornamenti e reload |
| Percorsi | Più percorsi per paziente, stati, setting, documenti, PRIAMO/FKT, stabilità e aggiornamenti longitudinali | Sorgente conservato; test end-to-end **NON ESEGUITI** | Percorsi OPEN multipli, aggiornamenti, chiusure e date amministrative/cliniche |
| Strutture e contatti | Catalogo, alias, canali, contatti multipli, risposte, solleciti, correzioni e mappa Leaflet | Bridge aggiunge una vista per struttura e la chiusura automatica delle richieste attive dello stesso percorso dopo accettazione; **solo test isolato JS** della chiusura | Flussi di contatto/risposta/correzione, seconda accettazione, audit e interazione mappa |
| OdC oggi e Lista OdC | Presenze, lista, ingressi, dimissioni, programmazione a 14 giorni e valutazioni NEWS2/IADL/ICA | Sorgente conservato; nessuna verifica UI o clinica | Conteggi e formule contro protocolli approvati, entrate/uscite e storici |
| Hospice | Consulenza, idoneità, documentazione, destinazione, esito e ingresso effettivo | Sorgente conservato; **NON VERIFICATO** | Accettazione distinta da ingresso, esiti e cronologia |
| Cruscotto, qualità, rettifiche e Dati & backup | Indicatori, qualità, storico, export, apertura/merge e backup JSON cifrati R8 | Interfaccia incorporata; la sincronizzazione automatica usa snapshot cifrati SQLite locale; UI, merge e download **NON VERIFICATI** | Conteggi distinti, round trip import/export, merge, ripristino, errori e archivi grandi |
| Per reparto (aggiunta) | Percorsi e strutture associate filtrabili per reparto | Presente nel bridge; **NON VERIFICATO** nel browser | Reparto/presidio/periodo, collocazione attuale, casi e collegamenti |
| Reparto × struttura | La matrice richiesta non è implementata | **MANCANTE** | Conteggi per richiesta, drill-down e riconciliazione con le viste di dettaglio |

## Modello dati e persistenza osservati

Il payload R8 V3.2 dichiara queste raccolte: `patients`, `hospitalEpisodes`, `cotConsultations`, `dischargePathways`, `odcWaitingList`, `odcStays`, `odcAssessments`, `facilityContacts`, `events`, `audit`, `revisions`, `cotCases`, `cotCaseLinks`, `cotCaseReconciliation`, oltre a `config` e `meta`. L'HTML contiene controlli di compatibilità e migrazione; questo audit non ha aperto archivi reali né verificato la conservazione dei record su importazione reale.

`app.py` monta l'intera pagina HTML come componente Streamlit. `frontend/cot_streamlit_bridge.js` riusa la cifratura browser R8 e invia al server l'intero snapshot cifrato dopo le modifiche. `storage.py` conserva revisioni append-only in SQLite e rifiuta scritture con revisione attesa obsoleta. Il test automatico copre il conflitto concorrente fra due scritture, ma non è un collaudo multiutente del componente/browser.

Problemi ancora aperti:

- SQLite locale contiene snapshot cifrati, non un database relazionale operativo, e non è affidabile su Streamlit Community Cloud.
- Ogni salvataggio ricrea e trasferisce l'intero archivio cifrato; il limite applicativo attuale è 15 MiB. Paginazione, query selettive e F-02 non sono implementati/verificati.
- Il controllo di revisione blocca una sovrascrittura concorrente, ma non esegue merge o riconciliazione automatica.
- Mancano autenticazione e ruoli, audit server-side verificabile, backup off-host, ripristino provato e PostgreSQL aziendale.
- `database.py`, `excel_io.py`, `backup_db.py` e `demo_data.py` appartengono al prototipo dati v0.3 e non sono collegati all'app Streamlit R8 (`app.py` importa soltanto `storage.py`). I loro test/benchmark descritti in `COLLAUDO_E_LIMITI_v0_3.md` non sono evidenza di parità o prestazioni dell'app corrente.
- Nessun archivio sanitario reale deve essere usato in questo ambiente o caricato su GitHub/Streamlit Community Cloud.

## Piano di migrazione dati (non ancora eseguito)

1. Inventariare versione, schema, raccolte, dizionari e relazioni direttamente da ogni archivio R8; calcolare conteggi e fingerprint senza cambiare il sorgente.
2. Decifrare solo in un ambiente aziendale autorizzato e produrre un rapporto di validazione per ID, riferimenti orfani, duplicati e campi non riconosciuti. Conservare ID, timestamp, stati, audit, revisioni ed eventi originali.
3. Importare in staging transazionale, mantenendo il payload sorgente e la provenienza per record. Nessun mapping di identità, deduplica o conversione di `MAP`, `@` o stati storici senza decisione esplicita e tracciata.
4. Riconciliare i casi dubbi con decisioni versionate e attore/data/motivazione; bloccare la promozione se resta un conflitto o un riferimento non spiegato.
5. Confrontare dopo l'importazione conteggi per raccolta, ID, fingerprint semantici, riferimenti e distribuzioni di stato; provare ripristino e rollback su copie sintetiche prima di qualsiasi archivio autorizzato.
6. Solo dopo la parità approvata, importare in PostgreSQL aziendale con vincoli referenziali, transazioni, audit, backup e prova F-02. Excel resta un formato d'interoperabilità.

Non è presente un importatore relazionale R8 nel codice corrente; i passaggi sopra sono un piano, non funzionalità implementate.

## Verifiche eseguite in questo ciclo

- `python3 -m unittest discover -s tests -v`: test storage, revisione concorrente, ignore dei dati locali e integrità del riferimento R8.
- `node tests/test_autoclose.js`: chiusura limitata alle altre richieste attive dello stesso percorso; altri percorsi e stati non attivi restano invariati; ripetizione idempotente.
- `node --check frontend/cot_streamlit_bridge.js`: sintassi JavaScript valida.
- Avvio effettivo e rendering iniziale del gate R8 in Chrome: **PASS**. Test delle schermate operative e flussi end-to-end: **NON ESEGUITI** perché il test è stato fermato al gate cifrato, senza impostare una password di prova.

Nessun test qui sopra attesta il superamento F-02, la validazione clinica di NEWS2/IADL/ICA, la migrazione completa degli archivi reali o l'idoneità alla produzione.
