// Isolated regression test for R8 adapter's acceptance cascade.
const fs=require('node:fs'), vm=require('node:vm'),assert=require('node:assert/strict');
const text=fs.readFileSync(__dirname+'/../frontend/cot_streamlit_bridge.js','utf8');
const start=text.indexOf('  function autoCloseContacts(winner) {');
const end=text.indexOf('  const priorSaveResponse=',start);
assert(start>=0 && end>start, 'function not found');
const source=text.slice(start,end);
const contacts=[
 {id:'W',patientId:'P',pathwayId:'PATH1',facilityId:'A',outcome:'Accettato',responseAt:'2026-11-17'},
 {id:'B',patientId:'P',pathwayId:'PATH1',facilityId:'B',outcome:'In attesa'},
 {id:'C',patientId:'P',pathwayId:'PATH1',facilityId:'C',outcome:'Nessun riscontro'},
 {id:'D',patientId:'P',pathwayId:'PATH1',facilityId:'D',outcome:'Rifiutato - criteri clinici'},
 {id:'E',patientId:'P',pathwayId:'PATH2',facilityId:'E',outcome:'In attesa'},
 {id:'F',patientId:'OTHER',pathwayId:'PATH3',facilityId:'F',outcome:'In attesa'},
 ];
const events=[];const revisions=[];
const context={
 db:{facilityContacts:contacts},R8_ACCEPTED:'Accettato',ACTIVE_STATUSES:new Set(['Accettato','In attesa','Nessun riscontro']),
 facilityLabel:(id)=>id, deep:x=>JSON.parse(JSON.stringify(x)),
 recordRevision:(...a)=>revisions.push(a),addEvent:(...a)=>events.push(a),
 setDirty:()=>{},refreshAll:()=>{},renderPatientDetail:()=>{},selectedPatientId:null,toast:()=>{}
};
vm.createContext(context);vm.runInContext(source,context);
assert.equal(context.autoCloseContacts(contacts[0]),2);
assert.equal(contacts[1].outcome,'Richiesta ritirata');
assert.equal(contacts[2].outcome,'Richiesta ritirata');
assert.equal(contacts[3].outcome,'Rifiutato - criteri clinici');
assert.equal(contacts[4].outcome,'In attesa');
assert.equal(contacts[5].outcome,'In attesa');
assert.equal(revisions.length,2);assert.equal(events.length,2);
assert.equal(context.autoCloseContacts(contacts[0]),0, 'repeated save must be idempotent');
console.log('PASS: auto-close only competing requests in same pathway; others preserved.');
