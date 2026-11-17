/*
 * COT R8 -> Streamlit parity adapter (experimental).
 * This add-on does not replace, remove or rewrite R8's views and forms.
 * Browser encrypts snapshots with the existing R8 crypto; only the encrypted
 * envelope is transported to the Streamlit Python backend.
 * Not approved for processing real patient data on Community Cloud.
 */
(function () {
  'use strict';
  let serverRevision = 0;
  let serverEnvelope = null;
  let serverAck = null;
  let pending = null;
  let pendingTimer = null;
  let serverAvailable = false;
  let readyTimer = null;
  let readyAttempts = 0;
  let backendStatus = 'Non connesso';
  const R8_ACTIVE = new Set(['In attesa', 'Nessun riscontro']);
  const R8_ACCEPTED = 'Accettato';
  const ACTIVE_STATUSES = new Set([...R8_ACTIVE, R8_ACCEPTED]);
  let lastAckId = null;
  let restoringFromServer = false;

  const id = x => document.getElementById(x);
  const post = (type, extra={}) => window.parent.postMessage({isStreamlitMessage: true, type, ...extra}, '*');
  const sendValue = value => post('streamlit:setComponentValue', {value, dataType:'json'});
  const sendHeight = () => {
    if(!serverAvailable)return;
    post('streamlit:setFrameHeight', {height:Math.max(850,document.documentElement.scrollHeight,document.body.scrollHeight)});
  };
  const newId = () => 'cot-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2,10);

  function renderBridgeStatus() {
    let badge=id('r8StreamlitSync');
    if(!badge) {
      badge=document.createElement('span');
      badge.id='r8StreamlitSync';badge.className='security-state locked';
      badge.style.cssText='max-width:220px;white-space:normal;line-height:1.3';
      document.querySelector('.topbar .actions')?.prepend(badge);
    }
    if(badge){badge.textContent='● Streamlit: '+backendStatus;badge.title='Sincronizzazione del backup CIFRATO sul database del server (solo prototipo)';
      badge.style.color=/Errore|Conflitto|Non connesso/.test(backendStatus)?'#b42318':'#08752f';}
  }
  function addRestoreButton() {
    const gate=document.querySelector('#vaultGate .vault-actions');
    if(!gate)return;
    let demo=id('cotNewDemo');
    if(!demo){demo=document.createElement('button');demo.id='cotNewDemo';demo.type='button';demo.className='btn';demo.textContent='Crea archivio di prova';demo.title='Solo dati sintetici: non usare per pazienti reali';gate.appendChild(demo);demo.addEventListener('click',async()=>{try{await createVault();queueSnapshot();}catch(e){if(e?.message!=='annullato')toast(e?.message||'Impossibile creare demo');}});}
    demo.hidden=!!vaultOpen;
    let btn=id('restoreStreamlit');
    if(!btn){btn=document.createElement('button');btn.className='btn';btn.type='button';btn.id='restoreStreamlit';btn.textContent='Ripristina ultima sessione';gate.appendChild(btn);btn.addEventListener('click',restoreFromBackend);}
    btn.hidden=!serverEnvelope || !!vaultOpen;
    const gateTitle=document.querySelector('#r7GateTitle');if(gateTitle)gateTitle.textContent='Gestione COT';
  }
  async function restoreFromBackend() {
    if(!serverEnvelope)return;
    if(vaultOpen && dirty && !confirm('Esistono modifiche in memoria. Sostituire la sessione con quella salvata sul server?'))return;
    try {
      let env=JSON.parse(serverEnvelope);
      const file=new File([JSON.stringify(env)],'COT_ultima_sessione.json',{type:'application/json'});
      const previousOpen=openFile;
      /* The original R8 opens the encrypted envelope with the operator's password. */
      restoringFromServer=true;
      try { await previousOpen(file); } finally { restoringFromServer=false; }
      serverRevision=Number(window.__cotStreamlitLatestRevision||serverRevision);
      backendStatus='Sessione ripristinata';renderBridgeStatus();addRestoreButton();
    }catch(e){backendStatus='Errore ripristino';renderBridgeStatus();toast(e?.message||'Ripristino non riuscito');}
  }
  function queueSnapshot() {
    if(!vaultOpen || !sessionPassword || !serverAvailable)return;
    if(pendingTimer)clearTimeout(pendingTimer);
    pendingTimer=setTimeout(sendEncryptedSnapshot,1800);
  }
  async function sendEncryptedSnapshot() {
    pendingTimer=null;
    if(pending || !vaultOpen || !sessionPassword || !serverAvailable)return;
    let snapshot=null;
    const generation=r8Generation;
    try{
      backendStatus='Cifratura in corso';renderBridgeStatus();
      const io=r8PersistenceIO();
      snapshot=await io.createSnapshot();
      const env=await io.encryptSnapshot(snapshot);
      const envelope=JSON.stringify(env);
      /* Preserve multi-operator conflicts instead of overwriting silently. */
      const message={kind:'encrypted_snapshot',request_id:newId(),expected_revision:serverRevision,
        generation, envelope};
      pending=message;
      backendStatus='Salvataggio in corso';renderBridgeStatus();
      sendValue(message);
    }catch(e){backendStatus='Errore cifratura';renderBridgeStatus();console.error('COT sync',e);}
    finally {if(snapshot) snapshot.canonical='';}
  }
  function readRenderArgs(event) {
    if(!event?.data?.isStreamlitMessage || event.data.type!=='streamlit:render')return;
    serverAvailable=true;
    if(readyTimer){clearTimeout(readyTimer);readyTimer=null;}
    const args=event.data.args||{};
    const seenRevision=Number(args.revision||0);
    window.__cotStreamlitLatestRevision=seenRevision;
    if(typeof args.envelope==='string' && args.envelope)serverEnvelope=args.envelope;
    if(seenRevision===0 && !pending)serverEnvelope=null;
    const ack=args.ack;
    if(pending && ack && ack.request_id===pending.request_id && lastAckId!==ack.request_id){
      lastAckId=ack.request_id;
      const m=pending;pending=null;
      if(ack.ok){
        serverRevision=Number(ack.revision);
        backendStatus='Salvato sul server';
        /* The R8 local "dirty" flag also tracks the manual file backup. */
        if(r8Generation!==m.generation)queueSnapshot();
      }else{
        backendStatus='Conflitto o errore di salvataggio';
        console.warn('COT: snapshot non salvato:',ack.error);
        toast('Sincronizzazione bloccata: '+String(ack.error||'verificare versione server'));
      }
    }else if(!vaultOpen && !pending){
      serverRevision=seenRevision;
      backendStatus=seenRevision?'Backup disponibile':'Connessione pronta';
    } else if(!pending && seenRevision>serverRevision){
      /* A different workstation wrote a new revision. Do not auto-overwrite. */
      backendStatus='Conflitto: archivio aggiornato altrove';
    }
    renderBridgeStatus();addRestoreButton();sendHeight();
  }
  window.addEventListener('message',readRenderArgs);
  const announceReady=()=>{
    if(serverAvailable||readyAttempts>=40)return;
    post('streamlit:componentReady',{apiVersion:1});
    readyAttempts++;
    readyTimer=setTimeout(announceReady,250);
  };
  if(document.readyState==='complete')setTimeout(announceReady,100);
  else window.addEventListener('load',()=>setTimeout(announceReady,100),{once:true});
  const frameTick=()=>setTimeout(sendHeight,100);
  window.addEventListener('load',frameTick);
  window.addEventListener('resize',frameTick);
  try {new ResizeObserver(frameTick).observe(document.body);}catch(e){}

  const priorDirty=setDirty;
  setDirty=function(...args){const res=priorDirty(...args);queueSnapshot();return res;};
  const priorVault=setVault;
  setVault=function(...args){const r=priorVault(...args);addRestoreButton();return r;};
  const priorOpen=openFile;
  openFile=async function(file){
    if(serverEnvelope && !vaultOpen && !restoringFromServer && !confirm('Esiste già un backup sul server. Aprire un altro JSON lo sostituirà al prossimo aggiornamento. Continuare?'))return;
    await priorOpen(file);
    serverRevision=Number(window.__cotStreamlitLatestRevision||serverRevision);
    addRestoreButton();
    queueSnapshot();
  };
  const priorClose=lockArchive;
  lockArchive=function(...args){const r=priorClose(...args);addRestoreButton();return r;};

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
    getRevision:()=>serverRevision,getStatus:()=>backendStatus};
  renderBridgeStatus();addRestoreButton();sendHeight();
})();
