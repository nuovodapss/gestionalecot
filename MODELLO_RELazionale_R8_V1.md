# Modello relazionale longitudinale COT — schema e progetto

> Stato Ciclo 5: la realizzazione ZIP/CSV e XLSX lossless, i test e i limiti sono documentati in [ARCHIVIO_RELAZIONALE_CICLO5.md](ARCHIVIO_RELAZIONALE_CICLO5.md). Le sezioni seguenti conservano il razionale del modello iniziale.

## Decisione e stato

L'archivio è uno scambio locale controllato di XLSX o ZIP/CSV; nessun database remoto è presupposto. `relational_model.py` definisce il contratto `COT_RELATIONAL_1_0`; `relational_archive.py` esporta/importa i due formati con checksum e controlli di integrità. `capture_r8_source()` conserva il payload JSON e crea le proiezioni tipizzate. La normalizzazione automatica è sospesa dove R8 non documenta una relazione certa.

L'XLSX/CSV è in chiaro e non è adatto a dati identificativi reali senza approvazione, protezioni organizzative e cifratura a riposo. Gli ID, inclusi quelli che sembrano numeri, restano testo.

## R8 analizzato

La baseline è il payload `version: 3`, `meta.schema: COT_ODC_FLOW_V3_2`, con configurazione in `config` e 14 raccolte:

| Raccolta R8 | Contenuto/chiave nota | Destinazione logica iniziale | Ambiguità da non risolvere automaticamente |
|---|---|---|---|
| `patients` | `id`; anagrafica (`taxCode`/`cf`, `surname`, `name`, `birthDate`, residenza, creazione) | `patients` | Campi anagrafici aggiuntivi conservati nel JSON sorgente |
| `hospitalEpisodes` | `id`, `patientId`, `admittedAt`, stato, provenienza, reparto attuale, `wardHistory[]` | `hospital_episodes`, `location_events` | La provenienza non prova la sede attuale; uno snapshot non prova una data di trasferimento |
| `cotConsultations` | `id`, `patientId`, `hospitalEpisodeId`, `pathwayId`, richiesta/risposta, richiedente, appropriatezza e stato | `consultations` | Risposte e note restano con valori originali |
| `dischargePathways` | `id`, paziente/episodio/consulenza, `target`, `requestedAt`, setting, stato, chiusura, PRIAMO, FKT, Hospice, note | `pathways`; candidati `care_needs` e link solo dopo riconciliazione | R8 non ha un ID di bisogno autonomo. Non si crea un bisogno verificato per deduzione e non si uniscono percorsi OPEN |
| `odcWaitingList` | `id`, `patientId`, `pathwayId`, unità, date e stato | `odc_waitlist` | Programmazione ingresso distinta dall'ingresso effettivo |
| `odcStays` | `id`, `patientId`, `pathwayId`, unità, date, destinazione pianificata/effettiva | `odc_stays` | Una permanenza effettiva non chiude automaticamente altri bisogni |
| `odcAssessments` | `id`, `patientId`, `stayId`, scala/fase, data, valori, valutatore | `odc_assessments` | Il payload completo della scala è conservato, anche per campi variabili |
| `facilityContacts` | `id`, `patientId`, `pathwayId`, struttura/ID o nome storico, canali, invio, esito, risposta, motivo, auto-chiusura | `facility_requests`, `request_channels` | Richieste candidate sullo stesso percorso non sono sicuramente lo stesso bisogno: l'accettazione non chiude richieste legacy in importazione |
| `events` | `id`, `type`, paziente, `refType/refId`, `at`, label, `meta` | `clinical_events`, con estrazione tipizzata solo dove certa | `meta` e proprietà future restano JSON; data effettiva e registrazione non si confondono |
| `audit` | Tracce operative con shape dipendente dall'azione | `audit_events` + JSON integrale | Nessuna ricostruzione di campi mancanti |
| `revisions` | Rettifiche/versioni con target e valori prima/dopo | `revisions` | Le revisioni sono append-only; non sovrascrivono la fonte |
| `cotCases` | `id`, `patientId`, `createdAt`, `createdBy`, `schemaVersion` | `cot_cases` | Nessun campo di stato viene aggiunto |
| `cotCaseLinks` | collegamento, caso, target, ruolo, ATTACH/DETACH, supersessione, fonte/motivo | `cot_case_links` | Si conserva la catena storica dei link |
| `cotCaseReconciliation` | assegnazione o non assegnazione, target, caso/relazione, fonte/motivo, supersessione | `cot_case_reconciliation` | Le decisioni storiche non si ricalcolano |
| `config` | strutture, reparti, setting, OdC, COT, comuni e altri dizionari/chiavi applicative | `facilities`, `wards`, `settings`, `configuration_records` | Dizionari sconosciuti restano integri in JSON |
| `meta` e payload | versione/schema e metadati estensibili | manifest e `r8_source_records`/`r8_source_chunks` | Conservati per confronto e replay |

La validazione R8 di riferimento richiede anche che ID di caso e collegamenti siano univoci, che i link abbiano riferimenti ammessi e coerenti col paziente, e che le catene di supersessione non siano cicliche. Il validatore relazionale iniziale copre chiavi, date e FK; i controlli specifici per le catene vanno estesi insieme al mapping V3, prima del round-trip.

## Schema logico proposto

| Tabella | Scopo e relazioni |
|---|---|
| `patients` | Scheda anagrafica unica, molti episodi, consulenze, percorsi, bisogni ed eventi |
| `facilities`, `wards`, `settings` | Cataloghi con ID testo stabili; reparto può riferirsi a una struttura |
| `hospital_episodes` | Episodio, provenienza iniziale, data ricovero e reparto origine; nessuna collocazione attuale sovrascritta |
| `location_events` | Collocazioni e trasferimenti con data effettiva, data registrazione, fonte e certezza |
| `consultations` | Consulenza protetta distinta da episodio e percorso |
| `pathways` | Lavoro COT amministrativo, target, stato e chiusura; più OPEN consentiti per paziente |
| `care_needs` | Bisogno assistenziale autonomo con setting, stato, intervallo e qualità della prova |
| `pathway_needs` | Relazione molti-a-molti fra bisogni e percorsi, con data e certezza |
| `facility_requests` | Una richiesta per destinatario, percorso, bisogno opzionale, canale, stato, risposta e chiusura concorrente |
| `request_channels`, `request_events` | Canali multipli e storico append-only di risposte, solleciti, accettazioni e ritiri |
| `odc_waitlist`, `odc_stays`, `odc_assessments` | Attesa, permanenza effettiva e valutazioni separate |
| `clinical_events`, `audit_events`, `revisions` | Timeline, audit e rettifiche distinti, con data effettiva e di registrazione |
| `cot_cases`, `cot_case_links`, `cot_case_reconciliation` | Entità R8 mantenute come registri collegati |
| `configuration_records` | Dizionari/chiavi di configurazione non ancora tipizzati |
| `r8_source_records`, `r8_source_fields` | Copia integrale per record e payload più inventario dinamico dei campi e relativo mapping |

Le richieste di R8 che hanno un `pathwayId` lo mantengono. `need_id` rimane nullo finché non esiste una decisione esplicita di riconciliazione. In questo modo la nuova regola di chiusura per accettazione può essere applicata solo a richieste nuove o già collegate con certezza allo stesso bisogno. La chiusura amministrativa del percorso, l'accettazione e il trasferimento fisico restano eventi/stati distinti.

## Mapping campo per campo

`R8_FIELD_MAPS` in `relational_model.py` contiene i mapping semantici dei campi stabili. `capture_r8_source()` cataloga ricorsivamente ogni proprietà osservata, compresi oggetti e liste annidati, registrandone path e tipo JSON. Un campo senza mapping esplicito riceve `SOURCE_JSON (preserved; mapping reviewed per field)` e resta ricostruibile in `r8_source_records`/`r8_source_chunks`; non viene scartato né convertito a un valore clinico. Il payload completo è conservato anche come `__payload__`. I JSON sono suddivisi in blocchi massimo 30.000 caratteri e ricomposti solo dopo controllo SHA-256, così nessuna cella XLSX supera il limite standard di Excel. Questa regola rende verificabile l'inventario di tutte le proprietà di ogni archivio reale, le cui estensioni possono variare nel tempo.

Mapping semantici principali implementati nel registro:

| R8 proprietà | Nuova colonna/entità |
|---|---|
| `patients.id/taxCode/cf/surname/name/birthDate` | `patients.patient_id/tax_code/surname/given_name/birth_date` |
| `hospitalEpisodes.id/patientId/admittedAt/originMacro/originSite/originWard` | `hospital_episodes` |
| `hospitalEpisodes.currentWard*`, `wardHistory[]` | `location_events`; eventuali date sono effettive solo se espresse nella fonte |
| `cotConsultations.*` | `consultations`; gli ID R8 restano gli stessi |
| `dischargePathways.id/patientId/hospitalEpisodeId/target/requestedSettingId/requestedAt/status/outcomeAt/closureReason` | `pathways` |
| FKT, PRIAMO, Hospice, note e ulteriori campi `dischargePathways` | Conservati nel sorgente; estrazione tipizzata da completare senza perdita |
| `facilityContacts.id/pathwayId/facilityId/sentAt/outcome/responseAt/reason/autoClosedByContactId` | `facility_requests` |
| `facilityContacts.method/methods[]` | `request_channels` |
| `odcWaitingList.*`, `odcStays.*`, `odcAssessments.*` | Tabelle omonime normalizzate; payload completo scala in `payload_json` |
| `events.id/type/patientId/refType/refId/at/recordedAt/actor` | `clinical_events` |
| `audit.*`, `revisions.*`, `cotCases.*`, `cotCaseLinks.*`, `cotCaseReconciliation.*` | Tabelle dedicate; gli altri campi non tipizzati restano nel JSON di origine |
| `config.facilities[]/wards[]/settings[]` | Cataloghi; campi aggiuntivi rimangono anche in `configuration_records` |
| Restanti proprietà annidate di ogni collection, `config` e `meta` | `r8_source_records` + `r8_source_chunks` e `r8_source_fields.field_path` |

## Integrità già implementata

`validate_dataset()` controlla versione schema, presenza delle tabelle, colonne dichiarate, campi obbligatori, ID duplicati, date ISO, foreign key e coerenza dei collegamenti. Ammette più percorsi OPEN e non chiude storici all'importazione. `schema_manifest()` espone ordine/colonne/chiavi/FK, conteggi e codifica date/ID come testo; gli archivi applicano checksum ai file e alle fonti.

## Scelte motivate e non ancora implementate

- È stato aggiunto l'episodio come entità distinta: il vecchio prototipo metteva provenienza/reparto dentro al percorso.
- La richiesta include ora `pathway_id` e un `need_id` opzionale: il prototipo collegava solo il bisogno, insufficiente per l'audit del percorso.
- Canali, risposte e trasferimenti hanno relazioni/eventi autonomi: lo stato corrente non sostituisce lo storico.
- La migrazione non ricava date di attesa da `@`, non considera `MAP` come domicilio e non trasforma un'accettazione in ingresso.
- Niente auto-chiusura retroattiva dei record R8: manca il collegamento certo al bisogno in alcuni archivi.

## Prossime fasi

1. Collegare le API dell'archivio all'interfaccia/bridge Streamlit e verificare la persistenza end-to-end senza alterare la UI originale.
2. Estendere i mapping tipizzati solo sulla base di semantiche confermate; mantenere il payload completo canonico finché il round-trip non è provato.
3. Eseguire merge guidato, viste e benchmark F-02 nel contesto applicativo.
4. Fase D — viste struttura, reparto e matrice con unità di conteggio esplicite.
5. Fase E — browser, round-trip, merge guidato e benchmark F-02. Report COT 11/11/2026 utilizzabile solo su sorgenti autorizzate e anonimizzate; nessun valore aggregato sarà imposto.

## Limiti del primo intervento

Il Ciclo 5 produce ZIP/XLSX lossless e li verifica con fixture/test. Non collega ancora il modello alla UI e non certifica la riconciliazione F-02. I campi rimasti nel JSON sorgente non sono persi, ma richiedono una decisione di mapping prima di alimentare dashboard o automazioni.
