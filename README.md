# Gestionale COT — Streamlit con interfaccia R8 (parità di codice, prototipo)

**Versione:** `R8-parita-0.4-PILOT`
**Riferimento obbligatorio:** `COT_GESTIONALE_INTEGRATO_APRI_O_UNISCI_R8.html` fornito dall'utente.

## Obiettivo

La nuova app **deve sostituire** il gestionale R8, non semplificarlo. Per questa ragione `frontend/R8_ORIGINALE_IMMUTATO.html` è la copia originale byte-per-byte, mentre `frontend/index.html` contiene esattamente lo stesso codice più un solo riferimento allo script aggiuntivo `cot_streamlit_bridge.js`. CSS, maschere, modalità d'inserimento e funzioni R8 **non sono stati riscritti**.

### Funzioni R8 conservate nel sorgente

- Coda COT, ricerca, scheda paziente e navigazione per tab.
- Anagrafica pazienti, ricoveri, trasferimenti di reparto, correzioni storicizzate.
- Richiesta/aggiornamento Consulenza Dimissioni Protette e verifica appropriatezza.
- Percorsi multipli contemporaneamente OPEN; aggiornamenti longitudinali di clinical status, FKT, dimissibilità, documentazione e PRIAMO.
- Attribuzione, attenzionamento e altri canali multipli per struttura; risposte, correzioni, catalogo strutture.
- OdC oggi, lista OdC, programmazione ingressi e uscite, ospiti OdC.
- NEWS2, IADL e ICA per ricoveri OdC, con valutazioni longitudinali.
- Percorsi Hospice, stati ed esiti.
- Cruscotto, qualità dati, mappa Leaflet, indicazioni sulle coordinate.
- JSON cifrati R8, funzioni di apertura/merge, esportazioni analitiche, rettifiche e storico eventi.

**Attenzione:** la conservazione del codice R8 non equivale a un collaudo completo delle sue funzioni dentro un iframe Streamlit. La compatibilità end-to-end deve essere verificata prima dell'uso reale.

Lo stato schermata per schermata e i test ancora necessari sono tracciati in [PARITA_FUNZIONALE_R8.md](PARITA_FUNZIONALE_R8.md). In questo repository, Streamlit monta l'HTML R8 come componente e conserva localmente snapshot cifrati: non usa ancora il modello relazionale operativo descritto nel piano di migrazione. `.gitignore` esclude database, esportazioni e segreti locali; controlla comunque i file staged prima di ogni commit.

### Funzioni aggiunte rispetto all'R8

- **Per struttura:** richieste con stato, canali, paziente, reparto, setting, link alla scheda; conteggi di persone, percorsi, richieste.
- **Per reparto:** elenco percorsi e pazienti con tutte le strutture collegate; due percorsi OPEN sono permessi.
- **Chiusura automatica delle richieste concorrenti** alla registrazione di una risposta `Accettato` su un percorso: le altre richieste attive di **quel percorso** diventano `Richiesta ritirata`, con motivo e evento di chiusura automatica. Le richieste su altri percorsi del medesimo paziente non sono toccate. Una seconda accettazione richiede conferma.
- **Salvataggio automatico CIFRATO** via componente Streamlit: il browser usa la cifratura R8 esistente e invia al backend soltanto il contenitore cifrato, senza password né payload in chiaro. Lo SQLite locale mantiene le revisioni precedenti e blocca scritture concorrenti su versioni obsolete; il ripristino richiede la password dell'operatore.
- Pulsante di creazione archivio di prova sintetico e ripristino ultima sessione cifrata.

## Avvio sul Mac

1. Installa Python e Streamlit in un ambiente virtuale.
2. Nella cartella principale, esegui:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

3. Apri il browser sulla pagina indicata. La schermata interna sarà quella R8, con le voci aggiuntive «Per struttura» e «Per reparto».
4. Usa **esclusivamente dati sintetici**. Apri un JSON cifrato **sintetico** R8 oppure seleziona «Crea archivio di prova».

## Da GitHub Desktop a Streamlit Cloud

1. Crea il repository privato `nuovodapss/gestionale-cot` con GitHub Desktop.
2. Apri il repository nel Finder (`Repository → Show in Finder`).
3. Estrai lo ZIP e copia **il contenuto interno**, non la cartella contenitrice, alla radice del repository.
4. Verifica questa struttura:

```
gestionale-cot/
  app.py
  storage.py
  requirements.txt
  .gitignore
  .streamlit/config.toml
  frontend/index.html
  frontend/R8_ORIGINALE_IMMUTATO.html
  frontend/cot_streamlit_bridge.js
  tests/
```

5. In GitHub Desktop: `Commit to main` → `Push origin` o `Publish repository` se è nuovo.
6. In Streamlit Community Cloud seleziona `nuovodapss/gestionale-cot`, `main`, `app.py`.

**NON INSERIRE** nei commit: JSON operativi (anche cifrati), dataset reali, credenziali, database SQLite, CSV identificativi, backup ed export pazienti.

## Limiti bloccanti prima dell'uso ASST

1. **NO DATI REALI SU STREAMLIT COMMUNITY CLOUD**: nessun accesso clinico autorizzato, logging e controllo ruoli, retention, DPA, valutazione privacy/infrastruttura.
2. **SQLite in Streamlit Cloud NON È DURABILE.** Il salvataggio automatico è sufficiente per un collaudo locale, **non** per sostituire il JSON negli ambienti operativi. Il database aziendale persistente (es. PostgreSQL) è ancora da progettare/validare e installare.
3. Il salvataggio attuale conserva un **snapshot cifrato del database R8**, non un modello relazionale server-side interrogabile. La migrazione completa dei record R8 a tabelle con transazioni multioperatore resta da implementare. Il controllo di revisione evita sovrascritture silenziose ma non implementa merge concorrenti.
4. Browser/Streamlit non completamente collaudati in questa sessione; necessari test funzionali E2E (compresi download, mappa, iframe, aggiornamenti, ripristino, controlli concorrenti).
5. Verificare l'effettiva semantica dell'accettazione per ogni categoria di richiesta: attualmente chiude le altre richieste attive **legate al medesimo ID percorso**. In futuro un modello del bisogno assistenziale più dettagliato potrà richiedere una logica più fine.
6. Collaudo **F-02 bloccante**: carico, benchmark, memoria, interfaccia, import/merge, integrità e ripristino.
7. **Non sostituisce ancora la R8 in produzione**. Conservarla, con i JSON originali, fino a riconciliazione e collaudo.

## Test eseguiti

```bash
python3 -m unittest discover -s tests -v
node tests/test_autoclose.js
node --check frontend/cot_streamlit_bridge.js
```

Test automatici: integrità byte-per-byte del riferimento originale, wrapper Streamlit collegato al componente R8, validazione backup cifrato, rifiuto dei conflitti di revisione anche con due scritture concorrenti, conservazione delle versioni, esclusione dei dati locali da Git e chiusura delle richieste attive dello stesso percorso. Streamlit 1.51.0 è stato avviato con Python 3.12 e il gate R8 è stato osservato in Chrome; per scelta dell'utente non è stata impostata una password di prova. Schermate operative, flussi UI, mappe e ripristino nell'iframe restano **NON VERIFICATI**.
