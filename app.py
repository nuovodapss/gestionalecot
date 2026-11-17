"""COT Streamlit v0.3: operational prototype, not authorized for identifiable health data."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import database as db
from excel_io import export_workbook, import_preview_or_commit, parse_workbook

st.set_page_config(page_title='COT | Gestionale v0.3',page_icon='🏥',layout='wide',initial_sidebar_state='expanded')
db.init_db()
st.markdown('''<style>
.block-container{padding-top:1.3rem;max-width:1580px}
[data-testid="stSidebar"]{background:#edf5fb}
h1,h2,h3{color:#125179}
[data-testid="stMetric"]{background:#f5f9fd;border:1px solid #dce8f1;border-radius:11px;padding:11px}
</style>''',unsafe_allow_html=True)


def show(rows, cols=None, max_rows=2000):
    frame=pd.DataFrame(rows)
    if cols is not None: frame=frame.reindex(columns=cols)
    if len(frame)>max_rows:
        st.caption(f"Visualizzate {max_rows} righe su {len(frame)}. I dati rimangono nel database.")
        frame=frame.head(max_rows)
    st.dataframe(frame,hide_index=True,width='stretch')


def name(p):
    return f"{p.get('cognome','')} {p.get('nome','')} · {p['id_paziente']}"


def need_caption(n):
    return f"{n['id_bisogno']} · {n.get('cognome','')} {n.get('nome','')} · {n['setting_corrente']}"


def request_caption(r):
    return f"{r['id_richiesta']} · {r['denominazione']} · {r['stato_richiesta']}"


def banner():
    st.info('**Ambiente sperimentale locale.** Solo dati di prova o anonimizzati; manca autenticazione nominale, cifratura applicativa e infrastruttura aziendale approvata. Excel e database SQLite non sono cifrati.')


st.sidebar.title('🏥 COT')
st.sidebar.caption('Gestionale v0.3 · logica multi-percorso e multi-struttura')
section=st.sidebar.radio('Sezione',[
    'Panoramica','Per struttura','Per reparto','Per setting','Scheda paziente',
    'Operatività','Controllo qualità','Excel · Importa/Esporta'
])
st.sidebar.divider()
as_of=st.sidebar.date_input('Fotografia alla data',value=date.today(),help='Eventi clinicamente validi fino a questa data')
known_on=st.sidebar.date_input('Informazioni registrate entro',value=date.today(),help='Per un report come noto allora, imposta anche il limite della data di registrazione; per un report rettificato imposta oggi')
st.sidebar.caption('Un evento può essere registrato oggi e riferirsi a una data clinica precedente. Le due date restano distinte.')
st.sidebar.error('NON APPROVATO PER DATI SANITARI IDENTIFICATIVI')

needs=db.snapshot_needs(as_of,known_on)
requests=db.snapshot_requests(as_of,known_on)
paths=db.snapshot_paths(as_of,known_on)
waiting=[n for n in needs if n['attesa_attiva']]

if section=='Panoramica':
    st.title('Monitoraggio COT')
    banner()
    k=db.summary(as_of,known_on)
    a,b,c,d=st.columns(4)
    a.metric('Pazienti distinti in attesa',k['pazienti_distinti_in_attesa'])
    b.metric('Bisogni in attesa',k['bisogni_in_attesa'])
    c.metric('Percorsi OPEN',k['percorsi_open'])
    d.metric('Richieste attive',k['richieste_attive'])
    a,b,c=st.columns(3)
    a.metric('Attese >14 giorni · pazienti',k['attese_oltre_14_gg'])
    b.metric('Accettate senza ingresso',k['accettate_senza_ingresso'])
    c.metric('Attesa senza data',k['giorni_non_calcolabili'])
    st.caption('I quattro indicatori principali hanno denominatori diversi. Non sommare i pazienti fra strutture. Dopo ACCETTATA, le altre richieste attive dello stesso bisogno sono chiuse automaticamente; gli altri bisogni e percorsi restano indipendenti.')
    st.subheader('Pazienti e bisogni in attesa')
    mode=st.selectbox('Includi', ['Solo in attesa','Tutti i bisogni','Da verificare'])
    selected=waiting if mode=='Solo in attesa' else (needs if mode=='Tutti i bisogni' else [n for n in needs if n['verifica']=='DA_VERIFICARE'])
    show(selected,['id_paziente','cognome','nome','id_bisogno','setting_corrente','stato','attesa_dal','giorni_attesa','verifica','reparti_origine','sede_attuale','reparto_attuale','percorsi_collegati'])

elif section=='Per struttura':
    st.title('Vista per struttura di destinazione')
    st.caption('Una riga per richiesta. L’accettazione di una struttura chiude automaticamente le altre richieste attive per lo stesso bisogno, preservando eventi e gli altri bisogni del paziente.')
    allf=db.fetch_all('STRUTTURE')
    choices=[f['denominazione'] for f in allf]
    selected=st.multiselect('Seleziona una o più strutture',choices,default=[])
    statuses=st.multiselect('Stato richiesta', list(db.REQ_STATES),default=[])
    channel_filter=st.multiselect('Canale richiesto', list(db.CHANNELS),default=[])
    active_only=st.checkbox('Solo bisogni ancora in attesa',value=False)
    data=[r for r in requests if (not selected or r['denominazione'] in selected)
          and (not statuses or r['stato_richiesta'] in statuses)
          and (not channel_filter or any(ch in r['canali_correnti'].split('|') for ch in channel_filter))
          and (not active_only or r['attesa_attiva'])]
    a,b,c=st.columns(3)
    a.metric('Persone distinte',len({r['id_paziente'] for r in data}))
    b.metric('Bisogni distinti',len({r['id_bisogno'] for r in data}))
    c.metric('Richieste / candidature',len({r['id_richiesta'] for r in data}))
    if data:
        df=pd.DataFrame(data)
        grouped=df.groupby('denominazione').agg(pazienti=('id_paziente','nunique'),bisogni=('id_bisogno','nunique'),richieste=('id_richiesta','nunique')).reset_index()
        st.subheader('Riepilogo strutture')
        show(grouped)
    st.subheader('Pazienti associati alle strutture selezionate')
    show(data,['denominazione','id_paziente','cognome','nome','id_bisogno','setting_corrente','id_richiesta','stato_richiesta','canali_correnti','reparti_origine','sede_attuale','reparto_attuale','giorni_attesa','verifica'])

elif section=='Per reparto':
    st.title('Vista per reparto / collocazione')
    view=st.radio('Criterio di raggruppamento',['Provenienza dei percorsi collegati','Collocazione fisica verificata'],horizontal=True)
    st.caption('La provenienza storica NON certifica la presenza attuale nel reparto. Se manca un evento di collocazione, la sede corrente rimane non verificata.')
    data=[]
    for n in needs:
        if view.startswith('Provenienza'):
            # Origin may include multiple wards from multiple legitimate paths.
            labels=[r.strip() for r in n['reparti_origine'].split(',') if r.strip()] or ['Provenienza non documentata']
        else:
            labels=[f"{n['sede_attuale']} · {n['reparto_attuale'] or n['struttura_attuale']}" if n['sede_verificata'] else 'Sede attuale non verificata']
        for label in labels:
            row=dict(n)
            row['raggruppamento']=label
            row['n_strutture_coinvolte']=len({r['id_struttura'] for r in requests if r['id_bisogno']==n['id_bisogno']})
            data.append(row)
    selected=st.multiselect('Filtra reparti / collocazioni',sorted({n['raggruppamento'] for n in data}))
    only_wait=st.checkbox('Mostra solo attese in corso',value=True)
    data=[r for r in data if (not selected or r['raggruppamento'] in selected) and (not only_wait or r['attesa_attiva'])]
    a,b=st.columns(2)
    a.metric('Pazienti distinti nel filtro',len({r['id_paziente'] for r in data}))
    b.metric('Bisogni distinti nel filtro',len({r['id_bisogno'] for r in data}))
    if data:
        grouped=pd.DataFrame(data).groupby('raggruppamento').agg(pazienti=('id_paziente','nunique'),bisogni=('id_bisogno','nunique')).reset_index()
        show(grouped)
    st.subheader('Pazienti e strutture coinvolte')
    by_need={}
    for r in requests:
        by_need.setdefault(r['id_bisogno'],set()).add(f"{r['denominazione']} ({r['stato_richiesta']})")
    details=[]
    for row in data:
        x=dict(row);x['strutture_coinvolte']=' | '.join(sorted(by_need.get(x['id_bisogno'],set())))
        details.append(x)
    show(details,['raggruppamento','id_paziente','cognome','nome','id_bisogno','setting_corrente','attesa_dal','giorni_attesa','strutture_coinvolte','verifica'])
    st.caption('Un paziente con due reparti di provenienza può apparire in due gruppi; il totale complessivo usa comunque ID paziente distinti.')

elif section=='Per setting':
    st.title('Vista per setting assistenziale')
    scope=st.selectbox('Perimetro',['Non Hospice','Hospice','Tutti'])
    group=[n for n in needs if (scope=='Tutti' or ((scope=='Hospice') == ('hospice' in n['setting_corrente'].casefold())))]
    waiting_scope=[n for n in group if n['attesa_attiva']]
    settings=sorted({n['setting_corrente'] for n in group})
    selected=st.multiselect('Setting da visualizzare',settings)
    data=[n for n in group if (not selected or n['setting_corrente'] in selected)]
    current=[n for n in data if n['attesa_attiva']]
    a,b,c=st.columns(3)
    a.metric('Pazienti distinti in attesa',len({n['id_paziente'] for n in current}))
    b.metric('Bisogni in attesa',len(current))
    c.metric('Bisogni registrati nel filtro',len(data))
    if data:
        df=pd.DataFrame(data)
        group=df.groupby('setting_corrente').agg(pazienti=('id_paziente','nunique'),bisogni=('id_bisogno','nunique')).reset_index()
        show(group)
    st.subheader('Dettaglio per setting')
    show(data,['id_paziente','cognome','nome','id_bisogno','setting_corrente','stato','attesa_attiva','attesa_dal','giorni_attesa','verifica','reparti_origine','reparto_attuale'])
    st.caption('Hospice separato per default. La denominazione del setting è gestita in modo esplicito: codifiche legacy e note non vengono convertite automaticamente.')

elif section=='Scheda paziente':
    st.title('Scheda longitudinale del paziente')
    people=db.fetch_all('PAZIENTI')
    if not people:
        st.info('Nessun paziente disponibile.')
    else:
        selected=st.selectbox('Paziente',people,format_func=name)
        pid=selected['id_paziente']
        subpaths=[p for p in paths if p['id_paziente']==pid]
        subneeds=[n for n in needs if n['id_paziente']==pid]
        subrequests=[r for r in requests if r['id_paziente']==pid]
        a,b,c=st.columns(3)
        a.metric('Percorsi',len(subpaths))
        b.metric('Bisogni',len(subneeds))
        c.metric('Strutture coinvolte',len({r['id_struttura'] for r in subrequests}))
        st.subheader('Percorsi COT (possono essere OPEN contemporaneamente)')
        show(subpaths,['id_percorso','data_attivazione','provenienza','presidio','reparto','stato'])
        st.subheader('Bisogni e attese')
        show(subneeds,['id_bisogno','setting_corrente','stato','attesa_dal','giorni_attesa','verifica','percorsi_collegati'])
        st.subheader('Richieste a strutture')
        show(subrequests,['id_bisogno','denominazione','id_richiesta','stato_richiesta','canali_correnti','data_richiesta','ultimo_aggiornamento'])
        st.subheader('Timeline non distruttiva')
        show(db.get_patient_history(pid),['data_evento','registrato_il','fonte','entita','azione','note','operatore'])

elif section=='Operatività':
    st.title('Operatività: inserimento e follow-up')
    banner()
    operator=st.text_input('Operatore / identificativo di test *',value='TEST-OPERATORE')
    tabs=st.tabs(['Pazienti','Percorsi','Bisogni','Strutture','Richieste multiple','Aggiorna eventi','Collocazione e verifica'])
    with tabs[0]:
        with st.form('add_patient',clear_on_submit=True):
            a,b,c=st.columns(3)
            pid=a.text_input('ID paziente (facoltativo, generato se vuoto)')
            surname=b.text_input('Cognome o pseudonimo')
            first=c.text_input('Nome o pseudonimo')
            if st.form_submit_button('Salva paziente'):
                try:
                    newid=db.insert_record('PAZIENTI',id_paziente=pid,cognome=surname,nome=first)
                    st.success(f'Creato {newid}');st.rerun()
                except Exception as e:st.error(str(e))
        st.subheader('Dati dimostrativi')
        if st.button('Carica esempio sintetico (solo archivio vuoto)'):
            try:
                from demo_data import load_demo
                load_demo();st.success('Demo caricata.');st.rerun()
            except Exception as e:st.error(str(e))
    with tabs[1]:
        patients=db.fetch_all('PAZIENTI')
        if not patients:st.info('Creare prima un paziente.')
        else:
            with st.form('add_path',clear_on_submit=True):
                person=st.selectbox('Paziente',patients,format_func=name)
                a,b,c=st.columns(3)
                start=a.date_input('Data attivazione',key='path_start')
                origin=b.selectbox('Provenienza',['Ospedale','OdC','Domicilio','Altra struttura'])
                site=c.text_input('Presidio')
                a,b=st.columns(2)
                ward=a.text_input('Reparto/UO')
                admission=b.date_input('Data ricovero',value=None,key='path_admission')
                note=st.text_area('Note percorso',key='path_note')
                if st.form_submit_button('Crea nuovo percorso (anche se esistono altri OPEN)'):
                    try:
                        v=db.insert_record('PERCORSI',id_paziente=person['id_paziente'],data_attivazione=start,provenienza=origin,presidio=site,reparto=ward,data_ricovero=admission,stato_iniziale='OPEN',note=note)
                        st.success(f'Percorso {v} creato.');st.rerun()
                    except Exception as e:st.error(str(e))
            candidates=db.get_paths()
            if candidates:
                with st.form('path_status'):
                    p=st.selectbox('Aggiorna stato percorso',candidates,format_func=lambda x:f"{x['id_percorso']} · {x['cognome']} {x['nome']}")
                    state=st.selectbox('Nuovo stato',db.PATH_STATES)
                    eventdate=st.date_input('Data evento',key='path_state_date')
                    note=st.text_input('Motivazione',key='path_state_note')
                    if st.form_submit_button('Registra evento di percorso'):
                        try:
                            db.insert_record('EVENTI_PERCORSO',id_percorso=p['id_percorso'],data_evento=eventdate,stato=state,note=note,operatore=operator)
                            st.success('Evento registrato.');st.rerun()
                        except Exception as e:st.error(str(e))
    with tabs[2]:
        patients=db.fetch_all('PAZIENTI')
        if patients:
            with st.form('new_need'):
                patient=st.selectbox('Paziente',patients,format_func=name,key='need_patient')
                setting=st.text_input('Setting richiesto (es. Riabilitazione 56 / Lungodegenza 60)')
                start=st.date_input('Data inizio bisogno',key='need_date')
                relevant=[p for p in db.get_paths(patient['id_paziente'])]
                links=st.multiselect('Collega uno o più percorsi COT (facoltativo)',relevant,format_func=lambda x:x['id_percorso']+' · '+x['reparto'])
                if st.form_submit_button('Crea bisogno assistenziale'):
                    try:
                        bid=db.create_need_with_links(patient['id_paziente'],setting,start,[l['id_percorso'] for l in links],operator)
                        st.success('Creato bisogno '+bid);st.rerun()
                    except Exception as e:st.error(str(e))
        if needs:
            st.divider()
            with st.form('link_existing'):
                n=st.selectbox('Collega un altro percorso al bisogno',needs,format_func=need_caption)
                eligible=[p for p in db.get_paths(n['id_paziente']) if p['id_percorso'] not in set(n['percorsi_collegati'].split(','))]
                if eligible:
                    p=st.selectbox('Percorso da associare',eligible,format_func=lambda x:x['id_percorso']+' · '+x['reparto'])
                    dt=st.date_input('Data collegamento',key='link_date')
                    if st.form_submit_button('Collega percorso'):
                        try:
                            db.insert_record('PERCORSI_BISOGNI',id_percorso=p['id_percorso'],id_bisogno=n['id_bisogno'],data_collegamento=dt,operatore=operator)
                            st.success('Percorso collegato.');st.rerun()
                        except Exception as e:st.error(str(e))
                else:st.caption('Nessun altro percorso disponibile per questo paziente.')
    with tabs[3]:
        with st.form('new_facility',clear_on_submit=True):
            a,b,c=st.columns(3)
            namef=a.text_input('Nome struttura (anche Altro)')
            kind=b.text_input('Tipologia')
            city=c.text_input('Comune')
            if st.form_submit_button('Aggiungi struttura'):
                try:
                    sid=db.insert_record('STRUTTURE',denominazione=namef,tipologia=kind,comune=city)
                    st.success(f'Struttura {sid} creata.');st.rerun()
                except Exception as e:st.error(str(e))
        show(db.fetch_all('STRUTTURE'))
    with tabs[4]:
        facilities=db.fetch_all('STRUTTURE')
        if not needs or not facilities:st.info('Servono almeno un bisogno e una struttura.')
        else:
            with st.form('multireq'):
                n=st.selectbox('Bisogno a cui inviare le richieste',needs,format_func=need_caption)
                selection=st.multiselect('Seleziona PIÙ strutture contemporaneamente',facilities,format_func=lambda x:x['denominazione'])
                channels=st.multiselect('Canali (selezione multipla)',db.CHANNELS,default=['Attenzionamento'])
                initial=st.selectbox('Stato iniziale delle nuove richieste', ['INVIATA','ATTENZIONATA','ATTRIBUITA','IN_ATTESA_RISPOSTA'])
                at=st.date_input('Data richiesta',key='request_date')
                note=st.text_area('Nota richiesta',key='request_note')
                if st.form_submit_button('Registra richieste verso le strutture selezionate'):
                    try:
                        if not selection:raise ValueError('Seleziona almeno una struttura.')
                        if not operator.strip():raise ValueError('Operatore obbligatorio.')
                        ids=db.create_requests_for_facilities(n['id_bisogno'],[f['id_struttura'] for f in selection],at,channels,note,operator,initial)
                        st.success(f'Create {len(ids)} richieste indipendenti.');st.rerun()
                    except Exception as e:st.error(str(e))
    with tabs[5]:
        if not needs:st.info('Prima creare un bisogno.')
        else:
            with st.form('need_event'):
                n=st.selectbox('Bisogno da aggiornare',needs,format_func=need_caption,key='event_need')
                kind=st.selectbox('Tipo evento',db.NEED_EVENT_KINDS)
                value=st.text_input('Valore (STATO: APERTA/SOSPESA/CONCLUSA/ANNULLATA; DIMISSIBILITA: AAAA-MM-GG)')
                event_date=st.date_input('Data dell’evento clinico',key='need_event_date')
                note=st.text_area('Nota',key='need_event_note')
                if st.form_submit_button('Aggiungi evento al bisogno'):
                    try:
                        db.insert_record('EVENTI_BISOGNO',id_bisogno=n['id_bisogno'],data_evento=event_date,tipo_evento=kind,valore=value,note=note,operatore=operator)
                        st.success('Evento aggiunto allo storico.');st.rerun()
                    except Exception as e:st.error(str(e))
        if requests:
            st.divider()
            with st.form('request_event'):
                r=st.selectbox('Richiesta da aggiornare',requests,format_func=request_caption)
                state=st.selectbox('Stato della singola richiesta',[v for v in db.REQ_STATES if v!='CHIUSA_PER_ALTRA_ACCETTAZIONE'])
                channels=st.multiselect('Canali di attribuzione / attenzionamento',db.CHANNELS)
                dt=st.date_input('Data evento struttura',key='request_event_date')
                note=st.text_area('Esito, riferimento o motivo',key='request_event_note')
                if state=='ACCETTATA':
                    try:
                        targets=db.preview_acceptance_closures(r['id_richiesta'],dt)
                        st.warning(f"Confermando ACCETTATA, il sistema chiuderà automaticamente **{len(targets)}** altre richieste attive dello stesso bisogno.")
                        if targets:
                            st.caption('Strutture coinvolte: '+', '.join(x['denominazione'] for x in targets))
                    except Exception as e:
                        st.error(str(e))
                    st.caption('I percorsi, gli altri bisogni e la collocazione fisica del paziente non cambiano.')
                if st.form_submit_button('Registra esito richiesta'):
                    try:
                        result=db.register_request_event(r['id_richiesta'],dt,state,'|'.join(channels),note,operator)
                        if result['chiuse']:
                            st.success(f"Accettazione registrata: chiuse automaticamente {len(result['chiuse'])} richieste concorrenti.")
                        else:
                            st.success('Esito registrato, con storico completo.')
                        st.rerun()
                    except Exception as e:st.error(str(e))
    with tabs[6]:
        patients=db.fetch_all('PAZIENTI')
        if patients:
            with st.form('patient_location'):
                person=st.selectbox('Paziente da localizzare',patients,format_func=name)
                at=st.date_input('Data collocazione',key='location_date')
                state=st.selectbox('Evento fisico',['PRESENTE','USCITO','NON_VERIFICATA'])
                a,b,c=st.columns(3)
                site=a.text_input('Sede / presidio')
                ward=b.text_input('Reparto / OdC')
                structure=c.text_input('Struttura (se applicabile)')
                note=st.text_area('Note sulla collocazione')
                if st.form_submit_button('Registra collocazione verificata'):
                    try:
                        db.insert_record('COLLOCAZIONI',id_paziente=person['id_paziente'],data_evento=at,presidio=site,reparto=ward,struttura=structure,stato=state,note=note,operatore=operator)
                        st.success('Collocazione storicizzata.');st.rerun()
                    except Exception as e:st.error(str(e))
        if needs:
            st.divider()
            with st.form('review_wait'):
                n=st.selectbox('Bisogno da verificare',needs,format_func=need_caption,key='review_need')
                result=st.selectbox('Esito verifica operatore',db.REVIEW_RESULTS)
                source=st.text_input('Fonte della verifica (obbligatoria)')
                dt=st.date_input('Data verifica',key='review_date')
                note=st.text_area('Motivazione / registrazione di rettifica')
                if st.form_submit_button('Conferma revisione'):
                    try:
                        db.insert_record('VERIFICHE',id_bisogno=n['id_bisogno'],data_evento=dt,esito=result,fonte=source,note=note,operatore=operator)
                        st.success('Verifica registrata, senza cancellare gli stati precedenti.');st.rerun()
                    except Exception as e:st.error(str(e))

elif section=='Controllo qualità':
    st.title('Qualità dei dati e verifiche')
    st.caption('Multi-percorso e multi-struttura sono normali e non generano allarmi. Controlliamo solo incongruenze puntuali o informazioni da confermare.')
    alerts=db.quality_alerts(as_of,known_on)
    a,b=st.columns(2)
    a.metric('Segnali di verifica',len(alerts))
    b.metric('Bisogni coinvolti',len({r['id_bisogno'] for r in alerts}))
    show(alerts)
    st.caption('La lista è una checklist di controllo, non certifica errori clinici. Le note non vengono interpretate automaticamente come trasferimenti o date.')

elif section=='Excel · Importa/Esporta':
    st.title('Importazione / esportazione Excel relazionale')
    banner()
    st.download_button('Scarica snapshot completo Excel',data=export_workbook(),file_name='COT_v03_snapshot.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.caption('Per il modello vuoto utilizzare COT_modello_importazione_v0_2.xlsx (compatibile v0.3) incluso nel pacchetto. Il file esportato contiene dati in chiaro.')
    up=st.file_uploader('Seleziona file Excel v0.2 / v0.3 con 11 tabelle',type=['xlsx'])
    if up is not None:
        try:
            content=up.getvalue()
            parsed=parse_workbook(content)
            report=import_preview_or_commit(parsed,commit=False)
            st.success('Schema verificato: nessun conflitto fra ID e dati esistenti.')
            show([{'tabella':label,**count} for label,count in report.items()])
            st.warning('L’import può aggiungere eventi automatici di chiusura per accettazioni presenti nel file. Le chiusure avvengono nella stessa transazione: conservare sempre un backup prima di confermare.')
            if st.button('CONFERMA IMPORTAZIONE',type='primary'):
                saved=import_preview_or_commit(parsed,commit=True)
                st.success(f'Importazione completa: {sum(v["nuove"] for v in saved.values())} nuove righe.');st.rerun()
        except Exception as e:st.error(f'Importazione respinta: {e}')
    st.divider()
    st.subheader('Limiti R7 e archivi reali')
    st.write('I JSON cifrati R7 non vengono convertiti automaticamente. Occorrono adattatore dedicato, migrazione di prova e riconciliazione di pazienti, percorsi, bisogni, strutture, eventi e note. Non effettuare importazioni operative identificative in questo prototipo.')
