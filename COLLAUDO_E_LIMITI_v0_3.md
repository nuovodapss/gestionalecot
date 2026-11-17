# Report di collaudo tecnico — COT Streamlit v0.3

Data di rilascio prototipo: 12 novembre 2026.

## Test automatici

Esecuzione: `python -m unittest discover -s tests -v`.

**21/21 PASS** (10 test di regressione di base + 11 test aggiuntivi sulla regola di accettazione):

- Due percorsi OPEN simultanei associati allo stesso paziente, senza allarme spurio.
- Tre richieste a strutture diverse riferite allo stesso bisogno, con persona distinta conteggiata una sola volta.
- Stato ACCETTATA diverso da INGRESSO_CONFERMATO; quando una struttura è ACCETTATA, le altre richieste attive dello stesso bisogno vengono chiuse atomicamente.
- Ingresso OdC con chiusura di un percorso ospedaliero e continuità del bisogno esterno.
- Ricostruzione dei cambiamenti tramite data clinica e filtro sulla data registrazione.
- Coerenza paziente tra percorso e bisogno in associazioni molti-a-molti.
- Invio multi-struttura atomico: se manca una struttura, nessuna richiesta parziale viene inserita.
- Trigger SQL di immutabilità su eventi longitudinali.
- Roundtrip Excel esporta → importa idempotente; conflitto su ID annulla l'intera importazione.
- Import diretto dell'Excel sintetico fornito; normalizzazione di timestamp convertiti da Excel.

## Mini-benchmark solo database, dati sintetici

Volume: **1.000 persone, 2.000 percorsi, 1.000 bisogni, 3.000 richieste a strutture, 8.000 eventi** (4.000 relativi ai bisogni + 4.000 alle richieste). Valori osservati in esecuzione locale isolata:

| Operazione | Tempo osservato |
|---|---:|
| Caricamento sintetico SQL in transazione | 0,106 s |
| Calcolo riepilogo e conteggi | 0,152 s |
| Estrazione lista delle 3.000 richieste | 0,054 s |
| Controlli qualità | 0,093 s |

Questi tempi **non sono tempi di interfaccia**, non includono import/export Excel o accesso concorrente, non sono misure ripetute e non costituiscono un collaudo prestazionale F-02. Variazioni di hardware, ambiente e densità degli eventi possono modificare sensibilmente i risultati.

## Test non eseguiti — stop all'uso operativo

- Avvio dell'interfaccia Streamlit nel browser e test utente multi-pagina: **non eseguito** in questo runtime (pacchetto Streamlit non installato).
- Test con JSON reali R7 e riconciliazione dei registri verificati: **non eseguito**.
- Validazione delle definizioni cliniche e degli indicatori contro i file originali: **non eseguita**.
- Test multiutente simultaneo su database PostgreSQL: **non eseguito**.
- Verifiche di autenticazione, profilazione, sicurezza, cifratura, rete ASST, backup off-host e DPO: **non eseguite**.

**F-02 resta APERTO e bloccante** prima di impiego operativo. SQLite e file Excel non cifrati esclusivamente per dati di prova/anonimizzati.

## Regola verificata nella v0.3

- Una richiesta `ACCETTATA` provoca nello stesso commit la chiusura delle altre richieste ancora attive dello stesso bisogno, senza intervenire su altri bisogni e percorsi.
- Eventi storici conservati; inserimento automatico con `operatore=SISTEMA` e causale che identifica la struttura accettata.
- Una seconda accettazione successiva chiude la struttura prima accettata.
- Chiusure già presenti negli export non vengono ricreate all’importazione.
- Accettazioni retrodatate e conflitti temporalmente incoerenti vengono bloccati.
- I test Python non equivalgono al collaudo del browser, della concorrenza multioperatore né F-02.
