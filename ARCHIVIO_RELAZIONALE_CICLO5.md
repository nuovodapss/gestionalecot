# Archivio relazionale COT — Ciclo 5

## Stato implementato

`relational_model.py` e `relational_archive.py` implementano lo schema `COT_RELATIONAL_1_0` e due formati di scambio lossless: ZIP con CSV e XLSX. Il JSON R8 V3.2 è la fonte canonica; le tabelle normalizzate sono proiezioni tipizzate verificate contro quella fonte. Gli edit supportati passano da `edit_r8_field()` e aggiornano insieme sorgente e proiezioni. Una modifica diretta incompatibile viene rifiutata in esportazione.

Le 26 tabelle sono 23 tabelle applicative e tre di staging: `r8_source_records`, `r8_source_chunks`, `r8_source_fields`. Le tabelle applicative coprono pazienti, strutture/reparti/setting, episodi e localizzazioni documentate, consulenze, percorsi, bisogni e collegamenti, richieste e canali, timeline clinica, OdC, audit, revisioni, casi, collegamenti e riconciliazioni, configurazione. L'archivio conserva anche ogni payload e riga R8 originale in JSON UTF-8 suddiviso in chunk verificabili.

## Contenuto dei file

### ZIP/CSV

- `tables/<nome_tabella>.csv`, uno per ciascuna delle 26 tabelle.
- `manifest.json`: versione schema, dizionario tabelle/colonne/FK, conteggi, codifica, hash SHA-256 e numero righe per CSV, inventario dei campi non mappati e regola sulla fonte canonica.
- `manifest.sha256`: checksum del manifest.

Ogni cella CSV contiene un valore JSON codificato: `null`, stringa vuota, stringhe, booleani, numeri, array e oggetti restano distinguibili. Gli ID sono stringhe anche quando sembrano numeri. Il CSV è UTF-8 con record CRLF. L'exporter scrive su un file temporaneo e sostituisce il file destinazione solo dopo scrittura completa.

### XLSX

Il workbook contiene un foglio per ognuna delle 26 tabelle, più `COT_MANIFEST`, `COT_DIZIONARIO` e `COT_BLOCCHI`. Le celle dati sono stringhe JSON, senza conversione automatica di ID/date in valori Excel o interpretazione come formule. Il foglio blocchi contiene parti di valori lunghi e metadati; l'importatore verifica ricomposizione e hash. La distribuzione è openpyxl (`openpyxl>=3.1,<4`).

### Limiti di importazione

ZIP e XLSX: massimo 100 MiB per file, 250 MiB espansi, 128 membri, 500.000 righe per tabella, controlli su path e rapporto di compressione. Gli importatori respingono formato/schema sconosciuto, file o fogli mancanti/extra, checksum errati, intestazioni non conformi, JSON non valido, duplicati, date non ISO, FK incoerenti, chunk non contigui e divergenze fra payload originale e tabelle proiettate. Un XLSX/ZIP è in chiaro: non contiene cifratura o password e va usato solo con dati sintetici o in un ambiente approvato e protetto.

## Semantica e compatibilità

- Le estensioni R8, i valori nulli/vuoti, i campi futuri e il payload radice sono preservati senza perdita e rientrano nel payload ricostruito.
- `need_id` e `pathway_needs` non vengono inferiti dalla semantica del percorso. La riconciliazione deve essere esplicita.
- Le richieste R8 `Nessun riscontro` restano distinte da `In attesa` come `NO_RESPONSE` e `AWAITING_RESPONSE`.
- Un `currentWard*` senza data effettiva resta uno snapshot sorgente; non viene convertito in un trasferimento. `wardHistory` produce eventi di localizzazione solo usando le date espresse nella fonte.
- Non si deducono occupazione corrente, ingressi/uscite, chiusure amministrative o relazioni di bisogno mancanti.
- Le tabelle applicative non rappresentabili in R8 V3.2 sono attualmente vincolate a rimanere vuote, quindi l'esportazione non può perdere scritture soltanto relazionali.
- Tutti i dati del fixture sono inventati e marcati con identificativi TEST; nessun archivio operativo o credenziale è incluso.

## Verifiche eseguite

Comando: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q`; anche `node tests/test_autoclose.js`, `git diff --check` e `py_compile`.

La suite Python comprende 24 test: schema/proiezione, round-trip ZIP e XLSX, payload lungo, write-through, validatore V3.2 estratto dall'HTML R8 immutato, drift, checksum, file mancanti, schema futuro, duplicati/FK/date errate, scrittura interrotta, fogli XLSX alterati/mancanti. Il benchmark è un singolo run locale, utile solo come misura iniziale. I valori sono millisecondi per singola chiamata, dimensione file e picco aggiuntivo Python `tracemalloc`, non memoria RSS:

| Pazienti | Righe | Staging / validazione | ZIP export / import / ricostruzione | XLSX export / import / ricostruzione | ZIP / XLSX bytes |
|---:|---:|---:|---:|---:|---:|
| 20 | 741 | 52.74 / 64.46 ms | 94.40 / 67.48 / 43.54 ms | 365.92 / 391.49 / 43.75 ms | 32,045 / 71,043 |
| 100 | 1,223 | 54.84 / 91.01 ms | 163.54 / 129.39 / 92.51 ms | 572.41 / 618.75 / 93.33 ms | 47,416 / 99,127 |
| 500 | 3,633 | 196.68 / 341.79 ms | 537.75 / 455.91 / 357.21 ms | 1,733.07 / 1,931.85 / 359.58 ms | 119,163 / 230,952 |

Al caso da 500 pazienti, il picco Python tracciato è 3.31 MB staging, 4.80 MB validazione, 10.23/10.68 MB ZIP export/import e 10.02/14.29 MB XLSX export/import. I valori completi per tutte le fasi sono prodotti da `tests/benchmark_relational_archive.py`; ciascuna misura è una singola esecuzione, quindi non è un benchmark di capacità né la certificazione F-02.

## Fuori ambito del Ciclo 5

Questo ciclo implementa e prova le API locali dell'archivio con fixture sintetiche; non le collega ancora ai controlli dell'interfaccia Streamlit, al bridge browser, alla persistenza multiutente o al merge operativo. Non è stata modificata `frontend/R8_ORIGINALE_IMMUTATO.html`. La struttura relazionale non è ancora un database operativo autonomo: per garantire il round-trip, l'R8 JSON resta il riferimento canonico. La chiusura completa F-02 richiede l'integrazione e il collaudo end-to-end successivi.
