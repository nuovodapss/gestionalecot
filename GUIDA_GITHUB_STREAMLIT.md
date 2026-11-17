# Pubblicare Gestionale COT v0.3 su GitHub e Streamlit

## Stato di questa consegna
Pacchetto **solo per collaudo**, con codice e due fogli Excel sintetici. Non contiene pazienti reali, database o credenziali.
**Non utilizzare l'app online per inserire dati sanitari identificativi.**

## A. Creare il repository nel nuovo account
1. Effettuare l'accesso come `nuovodapss` su GitHub.
2. Aprire <https://github.com/new>.
3. Owner: `nuovodapss`, nome: `gestionale-cot`, visibilità **Private**.
4. Non inizializzare con README o file .gitignore (sono già nel pacchetto). Premere **Create repository**.
5. Informare ChatGPT che il repository esiste: potrà verificare se il collegamento GitHub dispone di accesso in scrittura e caricare i file di testo. Per caricare tutti i file manualmente: estrarre questo ZIP; nella pagina del repository selezionare **uploading an existing file** oppure **Add file → Upload files** e trascinare i file e le cartelle *all'interno* di `gestionale-cot_GitHub` (non il solo .zip). Confermare con **Commit changes**.

## B. Collegare Streamlit Community Cloud
1. Aprire <https://share.streamlit.io> e collegare l'account GitHub.
2. Selezionare **Create app / New app**, scegliendo **Deploy from GitHub** quando richiesto.
3. Repository `nuovodapss/gestionale-cot`, branch `main`, main file path `app.py`.
4. Fare deploy; il servizio installa le dipendenze elencate in `requirements.txt`.
5. Nell'app usare **Operatività → Pazienti → Carica esempio sintetico** per vedere un esempio, senza utilizzare dati reali.

## ATTENZIONE: la versione v0.3 non è un gestionale online persistente
La v0.3 usa SQLite locale in `data/cot_v03.db`. Streamlit Community Cloud **non garantisce persistenza dei file locali**: aggiornamenti, riavvii o riconfigurazioni possono cancellare tutte le modifiche. L'app non prevede autenticazione nominale aziendale, ruoli, audit nominale protetto, cifratura, backup aziendale e migrazione certificata da R7. Le interazioni in Cloud sono esclusivamente dimostrative.

Prima di usare dati COT veri: architettura approvata dall'ASST con database persistente centralizzato (per es. PostgreSQL su infrastruttura aziendale), autenticazione, autorizzazioni IT/DPO e collaudo F-02. L'accesso privato al repo GitHub **non** equivale a protezione adeguata dei dati sanitari.

## Struttura dei file
- `app.py`: pagina iniziale dell'app Streamlit (entrypoint)
- `database.py`: modello relazionale, log eventi e transazioni
- `excel_io.py`: importazione/esportazione Excel
- `demo_data.py`: dati sintetici
- `requirements.txt`: librerie Python
- `.github/workflows/tests.yml`: test automatici ad ogni modifica
- `.streamlit/config.toml`: colori dell'interfaccia
- `tests/`: 21 test della logica relazionale
- `data/.gitkeep`: cartella predisposta, nessun database incluso

## Sorgenti e documentazione ufficiale
- <https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
- <https://docs.streamlit.io/develop/concepts/connections/connecting-to-data>
