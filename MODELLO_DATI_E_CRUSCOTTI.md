# Modello dati e viste — COT v0.3

## Cardinalità del dominio

```text
PAZIENTE (1) ── (N) PERCORSI COT (OPEN contemporanei ammessi)
     │
     └─────── (N) BISOGNI ASSISTENZIALI
                       │
         (N) PERCORSI_BISOGNI (N) ── (N) PERCORSI COT
                       │
                       └──── (N) RICHIESTE A STRUTTURA
                                      │
                                    (N) EVENTI DI RICHIESTA
```

La sede fisica **non si desume** dall'ultimo percorso: è un registro di `COLLOCAZIONI` relativo al paziente. I bisogni e i percorsi possono avere più eventi datati e non modificabili. `VERIFICHE` memorizza il parere professionale sulle attese e la sua fonte senza alterare i dati sorgente.

## Regole di dominio

1. Più percorsi OPEN per una persona: **ammessi e normali**. Un percorso può concludersi per trasferimento in OdC mentre un bisogno esterno rimane aperto e collegato ad altro percorso.
2. Più strutture per un bisogno: **ammesse e normali**. Per ogni relazione nasce un ID richiesta separato. La risposta di una struttura non cambia lo stato delle altre.
3. I canali `Attribuzione`, `Attenzionamento` e `Altro canale` sono multipli. In Excel usare `|` come separatore. L'ultimo evento della richiesta può aggiornare questi canali.
4. Lo stato `ACCETTATA` chiude automaticamente le altre richieste attive dello stesso bisogno, senza chiudere altri bisogni o percorsi. `ACCETTATA` non è `INGRESSO_CONFERMATO`. Anche l'ingresso confermato non chiude automaticamente un bisogno: richiede un evento di stato/attesa, oppure revisione.
5. La provenienza del percorso e il reparto attuale verificato sono entità distinte. I report di bed blocking non devono contare automaticamente l'origine come collocazione attuale.
6. Modifiche retrodatate: ogni evento possiede `data_evento` e `registrato_il`. Gli snapshot con limite di conoscenza consentono di confrontare la sequenza di eventi; vedi limitazioni per le tabelle principali nel README.
7. Qualità: segnalare lacune di sede, durata indeterminata, contrasti tra verifica e attesa, accettazione senza ingresso, conferma ingresso senza fine bisogno. **Non** segnalare una pluralità di percorsi o strutture in sé.

## Unità di conteggio: vietato confonderle

- **Persone distinte:** `COUNT(DISTINCT id_paziente)`; una persona è una sola anche se ha due bisogni, più percorsi o quattro strutture attenzionate.
- **Bisogni:** `COUNT(DISTINCT id_bisogno)`; un bisogno prosegue anche attraverso percorsi differenti se collegato esplicitamente.
- **Percorsi:** `COUNT(DISTINCT id_percorso)`; misurano il lavoro amministrativo.
- **Richieste/candidature:** `COUNT(DISTINCT id_richiesta)`; ogni struttura coinvolta per un bisogno rappresenta una richiesta indipendente, con storia dei suoi esiti.
- **Trasferimenti:** eventi effettivi `INGRESSO_CONFERMATO`, da validare rispetto a eventuali movimenti multipli; non sono equivalenti alle attribuzioni PRIAMO né agli esiti accettati.

### Esempio

PZ-DEMO-01 ha tre percorsi storici, di cui due OPEN; due bisogni ancora aperti; tre richieste indipendenti per BI-DEMO-1. Nella vista per struttura può comparire tre volte, ma nella card di persone distinte rimane una persona. Il totale delle persone su più strutture non è la somma delle righe di struttura.

## Esportazione Excel

Le 11 schede sono un export relazionale, **non** un unico foglio appiattito con duplicazione dei dati del paziente. Registri degli eventi esclusivamente append-only, con ID stabili. I dati contenuti in Excel sono sempre da considerarsi **in chiaro**.

## Report 11 novembre 2026

Non forzare i numeri `78 candidati → 68 non-Hospice (51 confermati tramite note + 17 ricostruiti)` nel codice. Sono risultati di verifica della reportistica precedente e un obiettivo di riconciliazione, non un dato costruibile dalle sole tabelle sintetiche. La certificazione richiede sorgenti R7 originali, note dell'operatore, cut-off e classificazioni allineate.

### Chiusura automatica delle richieste concorrenti (v0.3)

L’evento `ACCETTATA` è il trigger applicativo per aggiungere eventi `CHIUSA_PER_ALTRA_ACCETTAZIONE` su tutte le altre richieste **ancora attive per lo stesso id_bisogno**. Sono escluse le richieste già `RIFIUTATA`, `RITIRATA`, `CHIUSA_PER_ALTRA_ACCETTAZIONE` o `INGRESSO_CONFERMATO`. L’aggiornamento è transazionale e non determina il trasferimento fisico, la chiusura del bisogno o la chiusura dei percorsi COT. Se un nuovo esito accettato sostituisce quello precedente, quest’ultimo viene chiuso con un nuovo evento, senza eliminare la precedente accettazione dallo storico.
