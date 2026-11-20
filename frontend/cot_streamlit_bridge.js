/*
 * R8 ↔ Streamlit Components v1 adapter.
 * The page remains an isolated, registered Streamlit custom component because
 * R8 is a full standalone app with a large global DOM and CSS surface.
 * Streamlit 1.51.0 v1 message protocol: componentReady, render,
 * setComponentValue, and setFrameHeight. No SQLite autosave is used.
 */
(function () {
  'use strict';
  let disposed = false;
  let streamlitReady = false;
  let renderedByStreamlit = false;
  let pendingTimer = null;
  let frameHeightScheduled = false;
  let pendingRequestId = null;
  let lastCommandId = null;
  let deferredSessionState = null;
  let bridgeStatus = 'In attesa del bridge';
  let relationalMode = false;
  const R8_ACTIVE = new Set(['In attesa', 'Nessun riscontro']);
  const R8_ACCEPTED = 'Accettato';
  const ACTIVE_STATUSES = new Set([...R8_ACTIVE, R8_ACCEPTED]);
  const id = x => document.getElementById(x);
  const newId = () => 'cot-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2,10);
  const post = (type, extra={}) => {
    if (disposed || window.parent === window || !streamlitReady) return false;
    window.parent.postMessage({isStreamlitMessage:true,type,...extra}, window.location.origin);
    return true;
  };
  // Names mirror the documented Components v1 frontend helpers.
  const StreamlitV1 = {
    setComponentReady: () => {
      if (disposed || streamlitReady || window.parent === window) return;
      streamlitReady = true;
      window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:componentReady',apiVersion:1},window.location.origin);
    },
    setComponentValue: value => post('streamlit:setComponentValue',{value,dataType:'json'}),
    setFrameHeight: height => post('streamlit:setFrameHeight',{height}),
  };
  const sendValue = value => StreamlitV1.setComponentValue(value);
  function renderBridgeStatus(text) {
    if (text) bridgeStatus = text;
    let badge=id('r8StreamlitSync');
    if(!badge) {
      badge=document.createElement('span');
      badge.id='r8StreamlitSync';badge.className='security-state locked';
      badge.style.cssText='max-width:260px;white-space:normal;line-height:1.3';
      document.querySelector('.topbar .actions')?.prepend(badge);
    }
    if(badge){badge.textContent='● Streamlit: '+bridgeStatus;
      badge.title='Sessione volatile; esporta un archivio relazionale prima di chiudere.';
      badge.style.color=/Errore|non connesso|non riuscito/i.test(bridgeStatus)?'#b42318':'#08752f';}
  }
  function addRestoreButton() {
    const gateTitle=document.querySelector('#r7GateTitle');
    if(gateTitle)gateTitle.textContent='Gestione COT';
  }
  function setRelationalMode(enabled) {
    relationalMode=enabled;
    const save=id('saveEncrypted');
    let note=id('r8RelationalSaveNotice');
    if(save)save.disabled=enabled;
    if(enabled && save && !note) {
      note=document.createElement('span');
      note.id='r8RelationalSaveNotice';
      note.className='small muted';
      note.textContent='Archivio relazionale: usa “Prepara export” nel pannello Streamlit.';
      save.insertAdjacentElement('afterend',note);
    } else if(!enabled && note) note.remove();
    if(enabled)r8SetState('LOADED','Archivio relazionale non cifrato caricato in memoria; esporta il file prima di chiudere.');
  }
  function queueSnapshot() {
    if (pendingTimer) clearTimeout(pendingTimer);
    if (disposed) return;
    pendingTimer=setTimeout(()=>{
      pendingTimer=null;
      const event={kind:'session_state',event_id:newId(),open:!!vaultOpen,dirty:!!dirty,generation:Number(r8Generation||0)};
      if(!sendValue(event)) deferredSessionState=event;
    },180);
  }
  function setFrameHeight() {
    StreamlitV1.setFrameHeight(Math.max(850,document.documentElement.scrollHeight,document.body.scrollHeight));
  }
  function sendPayload(requestId) {
    if (!vaultOpen || !db || !renderedByStreamlit) {
      sendValue({kind:'bridge_error',event_id:newId(),request_id:requestId,command_kind:'export_payload',error:'Archivio R8 non aperto o bridge non pronto'});
      return;
    }
    try {
      const payload=JSON.parse(JSON.stringify(db));
      pendingRequestId=requestId;
      renderBridgeStatus('Invio snapshot R8 a Python');
      sendValue({kind:'r8_payload',event_id:newId(),request_id:requestId,payload});
    } catch(error) {
      sendValue({kind:'bridge_error',event_id:newId(),request_id:requestId,error:String(error?.message||error)});
    }
  }
  function openRelationalArchive(payload) {
    const issue=typeof cotV32RecordError==='function'?cotV32RecordError(payload):'Validatore R8 V3.2 non disponibile';
    if(issue) throw new Error(issue);
    const nextDb=migrateDb(JSON.parse(JSON.stringify(payload)));
    const save=id('saveEncrypted');
    const previous={db,vaultOpen,sessionPassword,dirty,protocol:r7SessionProtocol,generation:r8Generation,
      state:r8State,message:r8StateMessage,relationalMode,saveTitle:save?.title};
    try {
      db=nextDb;
      sessionPassword=null;
      r7SessionProtocol='RELATIONAL';
      dirty=false;
      r8Generation=Number(r8Generation||0)+1;
      initControls();
      refreshAll();
      setRelationalMode(true);
      setVault(true);
      if(id('saveEncrypted')) id('saveEncrypted').title='Archivio relazionale non cifrato: prepara export nel pannello Streamlit.';
      r8SetState('LOADED','Archivio relazionale non cifrato. I dati sono temporanei e restano in memoria.');
      r7ClearSaveNotice?.();
    } catch(error) {
      db=previous.db;sessionPassword=previous.sessionPassword;dirty=previous.dirty;
      r7SessionProtocol=previous.protocol;r8Generation=previous.generation;
      relationalMode=previous.relationalMode;r8State=previous.state;r8StateMessage=previous.message;
      if(save)save.title=previous.saveTitle||'';
      setRelationalMode(previous.relationalMode);setVault(previous.vaultOpen);
      try { initControls();refreshAll();r8UpdateIndicator(); } catch(restoreError) {}
      throw error;
    }
  }
  function loadRelationalPayload(args) {
    if(vaultOpen && dirty && !confirm('Le modifiche R8 correnti non sono ancora esportate. Sostituire la sessione?')) {
      sendValue({kind:'bridge_error',event_id:newId(),request_id:args.id,command_kind:'load_payload',error:'Caricamento annullato per proteggere le modifiche non esportate'});
      return;
    }
    pendingRequestId=args.id;
    openRelationalArchive(args.payload);
    renderBridgeStatus('Archivio relazionale non cifrato aperto');
    toast('Archivio relazionale validato e aperto · dati non cifrati');
    sendValue({kind:'loaded',event_id:newId(),request_id:args.id});
    queueSnapshot();
  }
  function handleCommand(command) {
    if(!command || typeof command.id!=='string' || command.id===lastCommandId)return;
    lastCommandId=command.id;
    try {
      if(command.kind==='probe') {
        pendingRequestId=command.request_id;
        bridgeStatus='Prova JavaScript → Python in invio';renderBridgeStatus();
        sendValue({kind:'probe',event_id:newId(),request_id:command.request_id,local_counter:Number(window.__cotBridgeLocalCounter||0)});
      } else if(command.kind==='load_payload') {
        loadRelationalPayload(command);
      } else if(command.kind==='export_payload') {
        sendPayload(command.request_id);
      }
    } catch(error) {
      renderBridgeStatus('Errore di caricamento');
      sendValue({kind:'bridge_error',event_id:newId(),request_id:command.request_id,command_kind:command.kind,error:String(error?.message||error)});
    }
  }
  const openEncryptedArchive=window.openFile;
  window.openFile=async function(file) {
    await openEncryptedArchive(file);
    setRelationalMode(false);
  };
  const closeArchive=window.lockArchive;
  window.lockArchive=function(...args) {
    const result=closeArchive(...args);
    if(!vaultOpen)setRelationalMode(false);
    return result;
  };
  function readRenderArgs(event) {
    if(disposed || event.source!==window.parent || event.origin!==window.location.origin
        || !event.data?.isStreamlitMessage || event.data.type!=='streamlit:render') return;
    renderedByStreamlit=true;
    const args=event.data.args||{};
    const ack=args.ack;
    if(ack && pendingRequestId && ack.request_id===pendingRequestId) {
      pendingRequestId=null;
      if(ack.ok) {
        if(ack.loaded) renderBridgeStatus('Archivio relazionale caricato');
        else if(ack.filename) renderBridgeStatus('Archivio verificato; download pronto');
        else renderBridgeStatus('Bridge bidirezionale confermato');
        if(ack.filename && relationalMode) {
          dirty=false;
          r8SetState('EXPORTED','Archivio relazionale verificato; download disponibile nel pannello Streamlit.');
        }
        window.__cotBridgeLocalCounter=Number(window.__cotBridgeLocalCounter||0)+1;
        if(ack.kind==='probe') sendValue({kind:'probe_ack',event_id:newId(),request_id:ack.request_id,
          local_counter:Number(window.__cotBridgeLocalCounter)});
      } else {
        renderBridgeStatus('Errore: esportazione/verifica non riuscita');
      }
    }
    handleCommand(args.command);
    if(deferredSessionState && !args.command) {
      const eventValue=deferredSessionState;
      if(sendValue(eventValue)) deferredSessionState=null;
    }
    if(!args.command && !pendingRequestId && !deferredSessionState && !window.__cotInitialStateSent) {
      window.__cotInitialStateSent=true;
      queueSnapshot();
    }
    setFrameHeight();
  }
  window.addEventListener('message',readRenderArgs);
  const announceReady=()=>{
    if(disposed || streamlitReady)return;
    requestAnimationFrame(()=>StreamlitV1.setComponentReady());
  };
  if(document.readyState==='complete')announceReady();
  else window.addEventListener('load',announceReady,{once:true});
  const resize=()=>{
    if(!renderedByStreamlit || disposed)return;
    if(frameHeightScheduled)return;
    frameHeightScheduled=true;
    requestAnimationFrame(()=>{frameHeightScheduled=false;if(!disposed)setFrameHeight();});
  };
  window.addEventListener('resize',resize);
  let resizeObserver=null;
  try { resizeObserver=new ResizeObserver(resize);resizeObserver.observe(document.body); } catch(error) {}
  window.addEventListener('pagehide',()=>{
    disposed=true;
    if(pendingTimer)clearTimeout(pendingTimer);
    resizeObserver?.disconnect();
    window.removeEventListener('message',readRenderArgs);
    window.removeEventListener('resize',resize);
  },{once:true});

  const priorDirty=setDirty;
  setDirty=function(...args){const res=priorDirty(...args);if(relationalMode)r8SetState('DIRTY','Modifiche non esportate; prepara un nuovo archivio.');queueSnapshot();return res;};
  const priorVault=setVault;
  setVault=function(...args){const r=priorVault(...args);addRestoreButton();queueSnapshot();return r;};
  const priorOpen=openFile;
  openFile=async function(file){
    await priorOpen(file);
    setRelationalMode(false);
    addRestoreButton();
    queueSnapshot();
  };
  const priorCreate=createVault;
  createVault=async function(...args){
    const result=await priorCreate(...args);
    setRelationalMode(false);
    queueSnapshot();
    return result;
  };
  const priorClose=lockArchive;
  lockArchive=function(...args){const r=priorClose(...args);queueSnapshot();return r;};

  /*
   * In R8, a dischargePathway is the boundary for competing facilities.
   * Multiple OPEN pathways for the same patient are LEGITIMATE.
   * Multiple active facility contacts are LEGITIMATE until one accepts.
   */
  function otherAccepted(pathwayId,winnerId) {
    return (db.facilityContacts||[]).filter(c=>c.pathwayId===pathwayId&&c.id!==winnerId&&c.outcome===R8_ACCEPTED);
  }
  function confirmCompetingAcceptance(pathwayId,winnerId) {
    const others=otherAccepted(pathwayId,winnerId);
    return !others.length || confirm('Un’altra struttura risulta già accettata per questo percorso. Confermare la nuova accettazione e chiudere l’accettazione precedente?');
  }
  function autoCloseContacts(winner) {
    if(!winner || winner.outcome!==R8_ACCEPTED)return 0;
    const at=winner.responseAt||new Date().toISOString().slice(0,10);
    const label=facilityLabel(winner.facilityId,winner.facilityLegacy||'');
    let count=0;
    for(const c of db.facilityContacts||[]){
      if(c.pathwayId!==winner.pathwayId||c.id===winner.id||!ACTIVE_STATUSES.has(c.outcome||'In attesa'))continue;
      const before=deep(c);
      c.outcome='Richiesta ritirata';
      c.responseAt=at;
      c.reason='Chiusura automatica per accettazione di '+label;
      c.autoClosedByContactId=winner.id;
      c.autoClosureReason='OTHER_FACILITY_ACCEPTED';
      recordRevision('FACILITY_CONTACT',c.id,before,deep(c));
      addEvent('FACILITY_REQUEST_AUTO_CLOSED',c.patientId,'facilityContact',c.id,at,
        'Richiesta chiusa per accettazione di '+label,
        {pathwayId:c.pathwayId,previous:before.outcome||'In attesa',current:c.outcome,
         winningContactId:winner.id,winningFacilityId:winner.facilityId,recordedAt:new Date().toISOString()});
      count++;
    }
    if(count){setDirty();refreshAll();if(selectedPatientId===winner.patientId)renderPatientDetail();toast('Accettata: chiuse automaticamente '+count+' altre richieste dello stesso percorso');}
    return count;
  }
  const priorSaveResponse=saveContactResponse;
  saveContactResponse=function(...args){
    const cid=id('contactResponseId')?.value;
    const target=db.facilityContacts.find(c=>c.id===cid);
    const to=id('contactResponseOutcome')?.value;
    if(target && to===R8_ACCEPTED && !confirmCompetingAcceptance(target.pathwayId,cid))return;
    const prior=target?.outcome;
    const r=priorSaveResponse(...args);
    const updated=db.facilityContacts.find(c=>c.id===cid);
    if(updated?.outcome===R8_ACCEPTED && prior!==updated.outcome)autoCloseContacts(updated);
    return r;
  };
  // wire() in the original R8 has already bound the old function reference.
  // Rebind this one handler to the adapter without altering the form.
  if(id('saveContactResponse'))id('saveContactResponse').onclick=(...args)=>saveContactResponse(...args);
  const priorSaveContact=saveContact;
  saveContact=async function(...args){
    const pathId=id('contactPathwayId')?.value;
    const to=id('contactOutcome')?.value;
    if(to===R8_ACCEPTED && !confirmCompetingAcceptance(pathId,null))return;
    const existing=new Set(db.facilityContacts.map(c=>c.id));
    const result=await priorSaveContact(...args);
    const created=db.facilityContacts.find(c=>c.pathwayId===pathId&&!existing.has(c.id)&&c.outcome===R8_ACCEPTED);
    if(created)autoCloseContacts(created);
    return result;
  };
  const priorCorrection=saveContactOutcomeCorrection51;
  saveContactOutcomeCorrection51=function(...args){
    const cid=id('contactOutcomeCorrectionId51')?.value;
    const c=db.facilityContacts.find(x=>x.id===cid);
    const to=id('contactOutcomeCorrectionValue51')?.value;
    if(c&&to===R8_ACCEPTED&&!confirmCompetingAcceptance(c.pathwayId,c.id))return;
    const previous=c?.outcome;
    const r=priorCorrection(...args);
    const updated=db.facilityContacts.find(x=>x.id===cid);
    if(updated?.outcome===R8_ACCEPTED && previous!==updated.outcome)autoCloseContacts(updated);
    return r;
  };

  /* R8-native visual language: new drill-down views, no replacement of existing pages. */
  const content=document.querySelector('.content');
  const nav=document.querySelector('.nav');
  if(content && nav){
    const template=`<section class="page" id="page-structureview"><div class="page-head"><div><h1>Per struttura</h1><p>Richieste, attenzionamenti, attribuzioni e accettazioni per struttura di destinazione.</p></div></div><div class="filters" style="margin-bottom:12px"><select id="r8StructureSelect"><option value="ALL">Tutte le strutture</option></select><select id="r8StructureStatus"><option value="ACTIVE">Attive (in attesa / nessun riscontro)</option><option value="ACCEPTED">Accettate</option><option value="CLOSED">Rifiutate / ritirate</option><option value="ALL">Tutte, incluso lo storico</option></select></div><div id="r8StructureKpis" class="kpis"></div><div class="card"><div class="card-head"><h2>Richieste per struttura</h2></div><div class="table-wrap" id="r8StructureTable"></div></div></section>
    <section class="page" id="page-wardview"><div class="page-head"><div><h1>Per reparto</h1><p>Pazienti e percorsi suddivisi per reparto registrato, con strutture coinvolte.</p></div></div><div class="filters" style="margin-bottom:12px"><select id="r8WardSelect"><option value="ALL">Tutti i reparti</option></select><select id="r8WardStatus"><option value="OPEN">Percorsi aperti</option><option value="ALL">Tutti i percorsi</option></select></div><div id="r8WardKpis" class="kpis"></div><div class="card"><div class="card-head"><h2>Elenco per reparto</h2></div><div class="table-wrap" id="r8WardTable"></div></div></section>`;
    content.insertAdjacentHTML('beforeend',template);
    const dash=nav.querySelector('button[data-page="dashboard"]');
    const addNav=(page,icon,label)=>{
      const btn=document.createElement('button');btn.type='button';btn.dataset.page=page;
      btn.innerHTML=`<span class="icon">${icon}</span><span class="label">${label}</span>`;
      btn.addEventListener('click',()=>showPage(page));
      nav.insertBefore(btn,dash);return btn;
    };
    addNav('structureview','▤','Per struttura');addNav('wardview','▥','Per reparto');
  }
  function allRequests(){
    return (db.facilityContacts||[]).map(c=>({c,p:db.dischargePathways.find(p=>p.id===c.pathwayId),person:patient(c.patientId)}));
  }
  const badgeKpi=(title,v,sub='')=>`<div class="kpi"><div class="label">${esc(title)}</div><div class="value">${v}</div><div class="sub">${esc(sub)}</div></div>`;
  const statusPill=(status)=>`<span class="badge ${status===R8_ACCEPTED?'green':R8_ACTIVE.has(status)?'amber':'red'}">${esc(status||'In attesa')}</span>`;
  const shortId=x=>esc(String(x||'').slice(-8));
  function renderStructureView(){
    if(!vaultOpen)return;
    const sel=id('r8StructureSelect'),preserve=sel.value;
    const facilities=(db.config?.facilities||[]).slice().sort((a,b)=>facilityLabel(a.id).localeCompare(facilityLabel(b.id)));
    sel.innerHTML='<option value="ALL">Tutte le strutture</option>'+facilities.map(f=>`<option value="${esc(f.id)}">${esc(facilityLabel(f.id))}</option>`).join('');
    sel.value=facilities.some(f=>f.id===preserve)?preserve:'ALL';
    const mode=id('r8StructureStatus').value;
    const rows=allRequests().filter(({c})=>(sel.value==='ALL'||c.facilityId===sel.value)&&(
      mode==='ALL'||(mode==='ACTIVE'&&R8_ACTIVE.has(c.outcome||'In attesa'))||(mode==='ACCEPTED'&&c.outcome===R8_ACCEPTED)||(mode==='CLOSED'&&!ACTIVE_STATUSES.has(c.outcome||'In attesa'))));
    const distinct=new Set(rows.map(x=>x.c.patientId));const paths=new Set(rows.map(x=>x.c.pathwayId));
    id('r8StructureKpis').innerHTML=badgeKpi('Pazienti distinti',distinct.size)+badgeKpi('Percorsi distinti',paths.size)+badgeKpi('Richieste',rows.length)+badgeKpi('Strutture',new Set(rows.map(x=>x.c.facilityId)).size);
    id('r8StructureTable').innerHTML=`<table class="table"><thead><tr><th>Struttura</th><th>Paziente</th><th>Reparto registrato</th><th>Setting</th><th>Canale</th><th>Data</th><th>Stato</th><th>Apri</th></tr></thead><tbody>${rows.map(({c,p,person})=>{
      const h=p&&currentHospEpisode(p),wardName=h?episodeWardLabel(h):'—';
      return `<tr><td>${esc(facilityLabel(c.facilityId,c.facilityLegacy))}</td><td>${esc(person?patientLabel(person.id):c.patientId)}</td><td>${esc(wardName)}</td><td>${esc(p?settingLabel(p.requestedSettingId):'—')}</td><td>${esc((c.methods||[c.method]).join(' · '))}</td><td>${fmtDate(c.sentAt)}</td><td>${statusPill(c.outcome)}</td><td><button class="btn tiny r8-open-patient" data-patient="${esc(c.patientId)}">Scheda</button></td></tr>`;
    }).join('')}</tbody></table>${rows.length?'':'<p class="small muted" style="padding:14px">Nessuna richiesta per i filtri scelti.</p>'}`;
    attachPatientButtons(id('r8StructureTable'));
  }
  function renderWardView(){
    if(!vaultOpen)return;
    const sel=id('r8WardSelect'),preserve=sel.value;
    const grouped=(db.dischargePathways||[]).map(p=>{
      const h=currentHospEpisode(p);
      return {p,h,wardName:h?episodeWardLabel(h):'Provenienza non documentata'};
    });
    const wards=[...new Set(grouped.map(x=>x.wardName))].sort((a,b)=>a.localeCompare(b));
    sel.innerHTML='<option value="ALL">Tutti i reparti</option>'+wards.map(w=>`<option value="${esc(w)}">${esc(w)}</option>`).join('');
    sel.value=wards.includes(preserve)?preserve:'ALL';
    const mode=id('r8WardStatus').value;
    const rows=grouped.filter(({p,wardName})=>(sel.value==='ALL'||wardName===sel.value)&&(mode==='ALL'||p.status==='OPEN'));
    const countPeople=new Set(rows.map(x=>x.p.patientId)).size;
    id('r8WardKpis').innerHTML=badgeKpi('Pazienti distinti',countPeople)+badgeKpi('Percorsi',rows.length)+badgeKpi('Reparti',new Set(rows.map(x=>x.wardName)).size)+badgeKpi('Richieste',rows.reduce((t,x)=>t+db.facilityContacts.filter(c=>c.pathwayId===x.p.id).length,0));
    id('r8WardTable').innerHTML=`<table class="table"><thead><tr><th>Reparto registrato</th><th>Paziente</th><th>Percorso</th><th>Setting</th><th>Strutture richieste</th><th>Stato</th><th>Apri</th></tr></thead><tbody>${rows.map(({p,wardName})=>{
      const contacts=db.facilityContacts.filter(c=>c.pathwayId===p.id);
      const structures=contacts.length?contacts.map(c=>`${facilityLabel(c.facilityId,c.facilityLegacy)} (${c.outcome||'In attesa'})`).join(' · '):'—';
      return `<tr><td>${esc(wardName)}</td><td>${esc(patientLabel(p.patientId))}</td><td>${shortId(p.id)}</td><td>${esc(settingLabel(p.requestedSettingId))}</td><td class="wrap">${esc(structures)}</td><td>${statusPill(p.status)}</td><td><button class="btn tiny r8-open-patient" data-patient="${esc(p.patientId)}">Scheda</button></td></tr>`;
    }).join('')}</tbody></table>${rows.length?'':'<p class="small muted" style="padding:14px">Nessun percorso per i filtri scelti.</p>'}`;
    attachPatientButtons(id('r8WardTable'));
  }
  function attachPatientButtons(host){host?.querySelectorAll('.r8-open-patient').forEach(btn=>btn.addEventListener('click',()=>openPatient(btn.dataset.patient)));}
  for(const filter of ['r8StructureSelect','r8StructureStatus'])id(filter)?.addEventListener('change',renderStructureView);
  for(const filter of ['r8WardSelect','r8WardStatus'])id(filter)?.addEventListener('change',renderWardView);
  const priorRender=renderPage;
  renderPage=function(page){if(page==='structureview')return renderStructureView();if(page==='wardview')return renderWardView();return priorRender(page);};
  const priorRefresh=refreshAll;
  refreshAll=function(...args){const r=priorRefresh(...args);if(vaultOpen){renderStructureView();renderWardView();}return r;};

  window.COT_STREAMLIT_BRIDGE_TEST={autoCloseContacts,queueSnapshot,renderStructureView,renderWardView,
    getStatus:()=>bridgeStatus,getHandshake:()=>({ready:streamlitReady,rendered:renderedByStreamlit}),
    getArchiveMode:()=>relationalMode?'RELATIONAL':'R8'};
  renderBridgeStatus();addRestoreButton();
})();
