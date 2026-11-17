# Migrazione dal gestionale HTML R7 — ancora DA VALIDARE

## Stato

**Non eseguita**. La v0.3 non interpreta direttamente i JSON cifrati R7, non ne richiede la password e non modifica gli archivi esistenti. Non dichiarare i dati migrati finché la riconciliazione non è stata completata.

## Workflow richiesto

1. Recuperare copie autorizzate degli export R7 e la versione HTML/schema usata dai diversi operatori e postazioni.
2. In ambiente approvato, decifrare i file senza esportare dati identificativi al di fuori dell'infrastruttura prevista. Registrare SHA-256 e versioni.
3. Inventariare le entità e i riferimenti: pazienti, percorsi, eventi, strutture alias, attenzionamenti, attribuzioni, stati richieste, movimenti, note, date e timestamp.
4. Distinguere le richieste contemporanee da una stessa struttura da eventuali ri-attribuzioni, rettifiche ed episodi nuovi, preservando ogni evento originale.
5. Mappare i percorsi verso i bisogni assistenziali; due o più percorsi OPEN per una persona NON sono duplicati di per sé. Una persona può legittimamente essere attenzionata da più strutture.
6. Generare Excel 11 tabelle con ID stabili e colonna di provenienza file/ID legacy nel registro tecnico di migrazione da sviluppare. Mai assumere che un testo in nota sia automaticamente un trasferimento clinico.
7. Importare in database di staging e confrontare per ogni fonte: conteggi di persone, percorsi, richieste e numero *integrale* di eventi, hash di record, stato storico e data conoscenza; isolare i conflitti.
8. Test clinico sui casi del registro verificato 11/11/2026, inclusi 78 candidati iniziali, 68 nello stock non-Hospice, 51 da note, 17 da dato documentale, pazienti con passaggio OdC, ingressi non chiusi, RSA e Hospice.
9. Verificare che il report al 27/10 e quello all'11/11 siano riproducibili con definizioni concordate e senza imporre numeri di output. Distinguere l'interpretazione delle note dalla maschera originale.
10. Solo dopo controlli F-02 (carico longitudinale, simultaneità, memoria, browser, throughput) e sicurezza aziendale proporre switch operativo.

## Stop conditions

- Anche un solo evento originale perso o sovrascritto senza tracciabilità.
- Un ID struttura o un percorso convertito arbitrariamente con ambiguità irrisolte.
- Un'assegnazione `ACCETTATA` trattata come ingresso reale senza evento/documentazione.
- Una conversione automatica di un movimento verso OdC in conclusione dell'attesa esterna.
- Risultati presentati come clinicamente certificati quando derivano soltanto da una proiezione di stati o note non validate.

**Non utilizzare il prototipo con dati identificativi reali.** La migrazione richiede autorizzazione IT/DPO e protezioni tecniche istituzionali.
