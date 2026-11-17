# Gestionale COT — Streamlit v0.3

**Prototipo locale di collaudo, NON idoneo all'uso con dati sanitari identificativi reali.**

Questa versione introduce la logica richiesta: **1 paziente → N percorsi OPEN indipendenti; 1 bisogno assistenziale → N percorsi collegati e N richieste parallele a strutture diverse**. Attribuzione e attenzionamento sono canali della richiesta; accettazione e ingresso effettivo sono eventi differenti. Le note e gli eventi pregressi non vengono cancellati.

## 1. Avvio

Richiede Python 3.11+; installare le dipendenze e avviare Streamlit:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Dal browser aprire l'URL locale indicato, normalmente `http://localhost:8501`.
In Windows, dopo aver installato le dipendenze, si può aprire `Avvia_COT_Windows.bat`. Su macOS si può usare `Avvia_COT_Mac.command` (se necessario eseguire dal terminale per consentire l'avvio).

I dati si salvano nel file locale `data/cot_v03.db`. L'interfaccia non dipende da JSON scaricati ogni volta. **Non cancellare la cartella `data`**. Il prototipo funziona su un solo PC e un database SQLite locale; non è una soluzione multioperatore aziendale.

## 2. Prova immediata

**Opzione A:** `Operatività → Pazienti → Carica esempio sintetico (solo archivio vuoto)`. Il pulsante è intenzionalmente bloccato se il database contiene già pazienti.

**Opzione B:** `Excel · Importa/Esporta →` caricare `COT_esempio_sintetico_v0_2.xlsx` (compatibile con la v0.3), controllare il riepilogo e confermare. Per l'inserimento da zero, usare `COT_modello_importazione_v0_2.xlsx` (compatibile con la v0.3) con intestazioni già definite.

Poi aprire `Per struttura`: il bisogno `BI-DEMO-1` coinvolge tre strutture, mentre un paziente è conteggiato una sola volta nella metrica di persone distinte. In `Scheda paziente` verificare che `PZ-DEMO-01` abbia due percorsi ancora OPEN e un precedente percorso CLOSED per passaggio a OdC, senza chiusura automatica dell'attesa esterna.

**Le due opzioni A e B sono alternative:** non caricare l'esempio Excel sopra una demo già creata con ID uguali ma diversi timestamp degli eventi. L'importatore bloccherà correttamente i conflitti anziché sovrascrivere.

## 3. Sezioni dell'app

- **Panoramica:** pazienti distinti, bisogni in attesa, percorsi OPEN, richieste attive, attese oltre 14 gg, accettate senza ingresso.
- **Per struttura:** selezione *multipla* delle strutture; dettaglio per richiesta, conteggio persone/bisogni/richieste, filtri di stato.
- **Per reparto:** scelta fra provenienza storica e collocazione fisica verificata; se non documentata, «Sede attuale non verificata».
- **Per setting:** liste separate, con Hospice distinto dagli altri setting.
- **Scheda paziente:** percorsi, bisogni, strutture ed eventi cronologici.
- **Operatività:** creare pazienti, più percorsi, bisogni collegati a più percorsi, aggiungere più strutture insieme, aggiornare singole richieste, registrare collocazione e verifica.
- **Controllo qualità:** incoerenze effettive (non multi-percorso e non multi-struttura).
- **Excel:** anteprima, importazione atomica e idempotente, esportazione di tutte le 11 tabelle.

## 4. Excel come formato di scambio, non come database condiviso

L'Excel è **un'importazione/esportazione esplicita**, non una tabella che tutti modificano simultaneamente. I fogli richiesti sono: `PAZIENTI`, `STRUTTURE`, `PERCORSI`, `BISOGNI`, `PERCORSI_BISOGNI`, `RICHIESTE`, `EVENTI_PERCORSO`, `EVENTI_BISOGNO`, `EVENTI_RICHIESTA`, `COLLOCAZIONI`, `VERIFICHE`.

- ID univoci e permanenti, trattati come stringhe.
- Una nuova modifica = nuova riga evento. Gli eventi sono *append-only* e protetti da trigger di immutabilità.
- Un ID già importato con contenuto **identico** non viene duplicato.
- Lo stesso ID con contenuto diverso **interrompe l'importazione dell'intero workbook**; non c'è mai un merge distruttivo automatico.
- Se una riga fa riferimento a un paziente, bisogno, percorso o struttura inesistente, l'importazione viene respinta.
- Non caricare il JSON cifrato R7 nel campo Excel: non è il formato corretto.

## 5. Indicatori e data indice

Nella barra laterale sono presenti due filtri temporali: **fotografia alla data** (quando il fatto clinico è avvenuto) e **informazioni registrate entro** (data limite in cui la modifica è stata inserita nel registro). I secondi filtri si applicano agli eventi, alle verifiche e alle collocazioni, e permettono confronti tra eventi conosciuti allora e rettifiche registrate successivamente.

**Limite attuale:** le tabelle di base (paziente, percorso, bisogno, richiesta, collegamento) non hanno ancora data di *ingestione*: la ricostruzione «come noto allora» è rigorosa per gli eventi ma non è una fotografia completa della conoscenza delle entità importate storicamente. L'estensione alle tabelle base è un requisito prima dei report certificati. Inoltre, se più eventi hanno la stessa data clinica e sono registrati in ordine errato, per ora la risoluzione usa la data/ora di inserimento.

`Pazienti distinti in attesa` = persone uniche con almeno un bisogno non concluso e un evento di inizio attesa non terminato oppure verifica esplicita confermata. Non coincide automaticamente con la prevalenza validata della COT e non considera i criteri complessi dei report R7 prima di una migrazione certificata. `Giorni attesa` = data fotografia − data evento `ATTESA_INIZIO`, **non** automaticamente data ricovero o dimissibilità. Per i bisogni confermati senza data di inizio, la durata non è calcolabile.

Una collocazione OdC non chiude automaticamente il bisogno o una richiesta esterna. Una richiesta ACCETTATA non equivale a ingresso. Una richiesta `INGRESSO_CONFERMATO` senza chiusura del bisogno è segnalata per verifica, non corretta automaticamente.

## 6. Copie di sicurezza

SQLite persiste oltre chiusura/standby del browser, ma il PC e il disco restano un singolo punto di guasto. Il file SQLite può usare il WAL: **non fare una copia a caldo del solo file `.db`**. Per il prototipo utilizzare il comando:

```bash
python backup_db.py
```

Il programma esegue la procedura di backup consistente fornita da SQLite, copiando il database in `backup_locali/`. Questo NON è un backup aziendale: va conservato in un ambiente protetto, e per dati reali occorrono backup automatici, cifratura, test di ripristino e policy IT.

## 7. Test

```bash
python -m unittest discover -s tests -v
```

Sono inclusi **21 test automatici** su percorsi concorrenti, richieste multiple, chiusura contestuale delle richieste attive dopo accettazione, sostituzione dell’accettazione, eventi immutabili, transizioni OdC, import Excel e rollback. Non è stato eseguito un collaudo dell’interfaccia Streamlit nel browser.

## 8. Limitazioni bloccanti prima della produzione

1. **Migrazione R7:** i JSON cifrati originali non sono qui disponibili in un formato direttamente convertibile. Occorre il mapping autorizzato di tutti gli ID/eventi, con prove sui casi del report 11/11/2026. La R7 non viene modificata né sostituita durante il collaudo.
2. **F-02 aperto:** test sistematico con volumi longitudinali reali, latenza UI, import/export, simultaneità e salvataggio; test browser non incluso in questo rilascio.
3. **Sicurezza:** mancano autenticazione nominale, permessi, cifratura applicativa e backup istituzionale. Nessun impiego identificativo senza autorizzazione IT/DPO.
4. **Multiutenza:** per uso aziendale, database PostgreSQL in infrastruttura ASST, con controllo transazionale e audit nominale.
5. **Definizioni cliniche e indicatori:** validare criteri di dimissibilità/stock, gestione Hospice, transizioni e anomalie, contro le fonti originali e revisioni dell'operatore.

Documenti: `MODELLO_DATI_E_CRUSCOTTI.md`, `MIGRAZIONE_R7_DA_VALIDARE.md`.


## Regola v0.3: una struttura accettata

Quando una richiesta passa a `ACCETTATA`, il database registra in un’unica transazione l’accettazione e la chiusura di tutte le altre richieste ancora attive **dello stesso bisogno** con stato `CHIUSA_PER_ALTRA_ACCETTAZIONE`. Ogni chiusura registra struttura accettante, richiesta originale, data e operatore nel log append-only. Richieste già rifiutate, ritirate o con ingresso confermato non vengono alterate. Gli altri bisogni e percorsi del paziente restano invariati e l’accettazione non equivale all’ingresso.

La registrazione di un’accettazione con data anteriore a eventi successivi dello stesso bisogno viene bloccata e richiede un procedimento di riconciliazione storica. L’importazione Excel riconcilia le accettazioni incluse nel file, senza duplicare eventuali chiusure già esportate, e applica tutto in una transazione. La migrazione dei JSON R7 resta da validare.


## Pubblicazione GitHub / Streamlit Community Cloud

Per pubblicare il solo prototipo: vedere [`GUIDA_GITHUB_STREAMLIT.md`](GUIDA_GITHUB_STREAMLIT.md). Il database SQLite su Cloud non è persistente e non può essere usato per dati clinici reali.
