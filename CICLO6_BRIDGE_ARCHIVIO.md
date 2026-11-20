# Ciclo 6 — Bridge R8 e archivio relazionale

## Bridge e scelta del componente

`app.py` registra l'HTML con `streamlit.components.v1.declare_component()` e lo monta con una chiave stabile. Non usa `components.html()` come iframe semplice. L'HTML ha un DOM globale esteso, CSS globale e funzioni R8 legacy; mantenere l'isolamento v1 riduce le collisioni con la pagina Streamlit. Components v2 esiste già in Streamlit 1.51.0 ma toglie l'iframe e richiederebbe il porting dell'intera R8 nel runtime di pagina v2. Per questa integrazione si mantiene il componente v1 registrato, supportato nella versione installata.

Fonti Streamlit, riferimento versionato all'installazione effettiva:

- [Introduzione ai componenti v1](https://docs.streamlit.io/1.51.0/develop/concepts/custom-components/components-v1/intro): registrazione `declare_component`, messaggi `componentReady`, `setComponentValue` e `setFrameHeight`, e ricezione degli argomenti Python nell'evento `render`.
- [API `st.components.v2.component`](https://docs.streamlit.io/1.51.0/develop/api-reference/custom-components/st.components.v2.component): API v2 presente ma con diverso modello di rendering e callback.

La causa individuata nel bridge precedente era il protocollo manuale senza un limite di ciclo di vita: timer ripetuti di handshake e resize potevano inviare messaggi dopo il deregistro del frame da parte di Streamlit. È la condizione che può produrre `Received component message for unregistered ComponentInstance`; la corrispondenza è coerente con il gestore Streamlit 1.51.0 che associa i messaggi alla finestra dell'iframe montato. Il difetto specifico non è stato riprodotto nel browser in questo ciclo.

Il nuovo adapter usa la sequenza v1 registrata: annuncio `componentReady` singolo dopo il caricamento, accetta `render` solo dalla finestra parent e dalla stessa origine, e invia valori/dimensioni solo nel ciclo di vita montato. `pagehide` ferma i timer, l'observer e i listener. Non aumenta i retry.

Il pulsante Streamlit **Verifica bridge** avvia un messaggio sintetico con ID richiesta. L'R8 iframe lo invia a Python tramite `setComponentValue`; Python salva l'ack nella sessione e il rerun lo ripassa come argomento al componente; il bridge mostra la conferma nel frame. La chiave stabile preserva il DOM R8 e la variabile locale del bridge durante il rerun. La prova è implementata, ma il risultato effettivo in browser resta da osservare.

## Importazione, modifica, esportazione

Flusso implementato:

1. `st.file_uploader` riceve ZIP o XLSX e l'importatore completo di Ciclo 5 verifica schema, checksum, conteggi, contenuti, FK e date prima di restituire lo stato.
2. Il payload R8 viene ricostruito e passato all'iframe tramite la chiamata del componente; il validatore V3.2 originale lo controlla prima di aprire la sessione R8.
3. Le operazioni esistenti della UI R8 aggiornano il suo payload, eventi e revisioni. `setDirty` invia a Python lo stato non esportato, senza scrivere un archivio.
4. **Prepara export** chiede uno snapshot corrente dell'R8. Python ricrea le proiezioni relazionali, valida, esporta ZIP/CSV oppure XLSX, reimporta il risultato e confronta dataset e payload ricostruito.
5. Solo dopo il confronto superato il download diventa disponibile e viene mostrato il SHA-256.

`app.py` non importa né usa `storage.py` e non scrive SQLite. I dati e il file generato restano in `st.session_state` solo per la sessione Streamlit; non c'è recupero temporaneo garantito dopo un'interruzione. Il testo UI avvisa che le modifiche non esportate possono perdersi e che l'offerta del download non prova la conservazione locale del file.

L'importazione JSON R8 cifrata e le opzioni originali di backup restano nella UI R8; il salvataggio JSON cifrato continua a funzionare per una sessione aperta tramite quel flusso. Quando è stata caricata una fixture relazionale senza password, il pulsante di backup cifrato viene disabilitato e l'operatore usa l'esportazione ZIP/XLSX.

## Fonte di verità e futura estensione

Nella transizione, il payload R8 V3.2 governa le operazioni della UI; `capture_r8_source()` ricrea tutte le proiezioni e `validate_r8_projection()` blocca divergenze. L'archivio relazionale esportato riparte dallo snapshot R8 corrente, non da una copia tabellare indipendente. Identificativi, campi annidati, eventi e revisioni non modificati restano nel payload canonico. Le tabelle `care_needs`, `pathway_needs` e `request_events` senza rappresentazione V3.2 non si eliminano e non si inferiscono: sono conservate solo se già rappresentate dalla fonte; nuove scritture non supportate sono rifiutate dall'exporter.

Estensione prevista per la migrazione successiva, non attiva in questa versione:

- inserire un namespace R8 esplicito, per esempio `meta.extensions.cotRelational`;
- assegnare `schema: COT_RELATIONAL_EXT_1` e `producerVersion` prima di aggiungere campi;
- introdurre `careNeeds[]` e `pathwayNeedLinks[]` con ID stabili, paziente, setting, stato, fonte, certezza, date effettiva/registrata, operatore e supersessione;
- imporre FK, unicità, transizioni e controllo incrociato patient↔pathway↔need, senza deduzioni dalla descrizione del percorso;
- mantenere una migrazione esplicita per i payload precedenti e conservare inalterato il payload sorgente fino alla verifica del round-trip. Le versioni dell'estensione non si sovrascrivono fra loro.

## Verifiche e stato

- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q`: 30 test Python superati, inclusi round-trip ZIP/XLSX dopo aggiunta di evento e revisione, rifiuto di input/formati incompatibili, contratto del bridge e rendering dell'entrypoint via Streamlit `AppTest`.
- `node tests/test_autoclose.js`: superato.
- `node --check frontend/cot_streamlit_bridge.js`, `py_compile` e `git diff --check`: superati.
- SHA-256 di `frontend/R8_ORIGINALE_IMMUTATO.html` invariato rispetto a `frontend/SHA256_R8.txt`.
- Streamlit 1.51.0 installato. Il codice usa la registrazione v1 compatibile con questa versione.
- L'app locale è stata avviata; l'interazione browser è stata respinta dal controllo automatico perché il tab selezionato puntava alla sessione privata `chatgpt.com`. Il controllo ha vietato l'uso di altri browser, Playwright o comandi indiretti per aggirare il blocco. Il test browser bidirezionale e lo scenario completo non sono quindi conteggiati come eseguiti.

## Limiti residui

I file ZIP/XLSX e il payload trasmesso al processo Python sono in chiaro. L'esportazione è un download e non una persistenza server permanente. Non sono implementati recupero in background, autenticazione/ruoli, audit multioperatore, merge concorrente o F-02. I dati sintetici non provano la piena compatibilità della UI con archivi operativi. Prima della prossima dichiarazione di completamento, il browser deve eseguire il probe bidirezionale con rerun, importare il file temporaneo generato dal comando sotto e completare la sequenza di modifica → export → nuova importazione → confronto.

Per preparare un file ZIP sintetico fuori dal repository:

```bash
.venv/bin/python tests/generate_relational_archive.py
```
