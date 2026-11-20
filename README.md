# Gestionale COT — Streamlit con interfaccia R8 (parità di codice, prototipo)

**Versione:** `R8-parita-0.5-PILOT`
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

Lo stato schermata per schermata e i test ancora necessari sono tracciati in [PARITA_FUNZIONALE_R8.md](PARITA_FUNZIONALE_R8.md). Streamlit monta l'HTML R8 come componente v1 registrato. Il flusso relazionale usa lo stato volatile della sessione e file ZIP/CSV o XLSX esportati e verificati; `app.py` non usa SQLite come archivio permanente. `.gitignore` esclude database, esportazioni e segreti locali; controlla comunque i file staged prima di ogni commit.

### Funzioni aggiunte rispetto all'R8

- **Per struttura:** richieste con stato, canali, paziente, reparto, setting, link alla scheda; conteggi di persone, percorsi, richieste.
- **Per reparto:** elenco percorsi e pazienti con tutte le strutture collegate; due percorsi OPEN sono permessi.
- **Chiusura automatica delle richieste concorrenti** alla registrazione di una risposta `Accettato` su un percorso: le altre richieste attive di **quel percorso** diventano `Richiesta ritirata`, con motivo e evento di chiusura automatica. Le richieste su altri percorsi del medesimo paziente non sono toccate. Una seconda accettazione richiede conferma.
- Importazione e validazione ZIP/CSV o XLSX, apertura nell'interfaccia R8 e preparazione dell'archivio aggiornato con controllo post-export e SHA-256.
- Prova manuale bidirezionale del bridge JavaScript → Python → conferma → JavaScript; il frame è un componente v1 con chiave stabile.
- L'importazione/apertura JSON R8 cifrato originale resta disponibile dentro l'interfaccia R8. Il salvataggio relazionale è un download; la sessione non conferma che il file sia stato conservato sul computer.

## Avvio sul Mac

1. Installa Python e Streamlit in un ambiente virtuale.
2. Nella cartella principale, esegui:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

3. Apri il browser sulla pagina indicata. La schermata interna sarà quella R8, con le voci aggiuntive «Per struttura» e «Per reparto».
4. Usa **esclusivamente dati sintetici**. Per creare un archivio relazionale di prova fuori dal repository:

```bash
.venv/bin/python tests/generate_relational_archive.py
```

Carica il file generato nel pannello Streamlit e seleziona «Valida e apri». Per i backup JSON cifrati R8, usa «Apri JSON cifrato» nell'interfaccia originale.

## Da GitHub Desktop a Streamlit Cloud

1. Crea il repository privato `nuovodapss/gestionale-cot` con GitHub Desktop.
2. Apri il repository nel Finder (`Repository → Show in Finder`).
3. Estrai lo ZIP e copia **il contenuto interno**, non la cartella contenitrice, alla radice del repository.
4. Verifica questa struttura:

```
gestionale-cot/
  app.py
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
2. **Lo stato della sessione non è permanente.** Nessun recupero temporaneo automatico è configurato: refresh, chiusura o interruzione prima dell'esportazione può perdere gli aggiornamenti.
3. ZIP/CSV e XLSX non sono cifrati; il payload completo passa dal browser al processo Python per l'esportazione. Solo fixture sintetiche finché non sarà approvato un ambiente protetto.
4. Le entità senza rappresentazione R8 V3.2 (bisogni assistenziali e link espliciti) non sono modificabili nell'UI né incluse come extension non versionate. La strategia di estensione futura è in [CICLO6_BRIDGE_ARCHIVIO.md](CICLO6_BRIDGE_ARCHIVIO.md).
5. Il bridge resta V1 isolato. La prova integrata del browser non è stata completata in questa sessione; controllo del flusso bidirezionale, mantenimento dello stato iframe, import visivo ed esportazione sono ancora da confermare nel browser autorizzato.
6. Riconciliazione multioperatore e merge conflitti non sono implementati; F-02 non è superato. Le chiusure automatiche continuano a operare entro lo stesso ID percorso secondo il comportamento R8 verificato separatamente.
7. **Non sostituisce la R8 in produzione.** Conservarla e usare solo fixture sintetiche fino al completamento di sicurezza, persistenza e collaudo.

## Test eseguiti

```bash
python3 -m unittest discover -s tests -v
node tests/test_autoclose.js
node --check frontend/cot_streamlit_bridge.js
```

Test automatici: integrità byte-per-byte del riferimento originale, wrapper Streamlit collegato al componente R8, validazione backup cifrato, rifiuto dei conflitti di revisione anche con due scritture concorrenti, conservazione delle versioni, esclusione dei dati locali da Git e chiusura delle richieste attive dello stesso percorso. Streamlit 1.51.0 è stato avviato con Python 3.12 e il gate R8 è stato osservato in Chrome; per scelta dell'utente non è stata impostata una password di prova. Schermate operative, flussi UI, mappe e ripristino nell'iframe restano **NON VERIFICATI**.
Test automatici Python: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q` (30 test, incluso Streamlit `AppTest`); JavaScript: `node tests/test_autoclose.js` e `node --check frontend/cot_streamlit_bridge.js`. Lo scenario visivo browser del Ciclo 6 è in attesa dell'autorizzazione del browser sull'origine locale.
