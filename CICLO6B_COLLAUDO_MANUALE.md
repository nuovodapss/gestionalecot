# Ciclo 6B — procedura di collaudo browser

## Fixture sintetica

Genera ZIP/CSV e XLSX validati, con 20 pazienti `TEST-*`, percorsi e richieste di prova:

```sh
.venv/bin/python tests/generate_cycle6b_fixture.py /tmp/cot-cycle6b-fixture
```

Il generatore verifica la struttura prima di scrivere i file. Non contiene credenziali e non legge archivi operativi.

## Esecuzione browser

1. Per isolare il bridge, avvia `.venv/bin/python -m streamlit run tests/streamlit_component_diagnostic.py --server.port 8502` e apri l’indirizzo locale nella sessione browser autorizzata. Il testo e il pulsante devono essere visibili; dopo un click Python deve mostrare la richiesta e il frame deve mostrare la conferma completa.
2. Avvia l'app nel repository con `.venv/bin/python -m streamlit run app.py --server.port 8501`.
3. Nella sessione Chrome dedicata apri `http://localhost:8501`; verifica visibilità, altezza del frame e assenza di errori console.
4. Premi “Verifica bridge” e continua solo dopo la conferma a quattro passaggi JavaScript→Python→JavaScript→Python.
5. Verifica il percorso JSON cifrato dalla UI R8: selezione del JSON, richiesta password, rifiuto di una password errata e apertura solo dopo decifratura valida.
6. Importa `cycle6b_synthetic.zip` da “Carica archivio relazionale”. Controlla manifest, checksum, schema, viste R8 e dicitura “Archivio relazionale non cifrato”.
7. Esegui le operazioni UI del ticket Cycle 6B. Prepara un export ZIP, scaricalo, poi reimportalo in una nuova sessione e confronta i payload completi. Ripeti con XLSX.
8. Ripeti dopo refresh e interrompendo la sessione prima dell’export. Controlla console Chrome e log Python; il download non prova la conservazione sul disco.

## Stato rilevato il 20 novembre 2026

La correzione del riferimento JavaScript `sendHeight()` rimosso è stata applicata. Il bridge minimo e quello R8 ora usano il protocollo Components v1, con altezza inviata dopo `streamlit:render`; il probe richiede la conferma di ritorno al backend prima di mostrare successo. Il test browser non è disponibile in questa sessione, quindi visibilità, dimensioni e handshake restano da dimostrare nel browser.

L'import ZIP/XLSX ora passa da `openRelationalArchive()`, eseguito dopo validazione Python e controllo R8 del payload; la modalità viene dichiarata esplicitamente non cifrata. Il JSON R8 mantiene il percorso originale di richiesta password e decifratura. La sessione Streamlit registra l'import come aperto solo dopo l'ack `loaded`; un errore conserva l'eventuale archivio precedente.
