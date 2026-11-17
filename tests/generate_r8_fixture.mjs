// Build a temporary, synthetic R8 archive using the encryptArchive function
// extracted from the immutable R8 source. The password and archive stay in /tmp.
import { readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import vm from 'node:vm';
import { randomBytes, webcrypto } from 'node:crypto';

const source = await readFile(new URL('../frontend/R8_ORIGINALE_IMMUTATO.html', import.meta.url), 'utf8');
const patients = Array.from({ length: 10 }, (_, i) => {
  const n = String(i + 1).padStart(2, '0');
  return {
    id: `TEST-PAT-${n}`, taxCode: `TEST-ID-${n}`, surname: 'PAZIENTE DI COLLAUDO',
    name: `SINTETICO ${n}`, birthDate: `195${i}-01-15`, homeCity: 'Citta Test',
    homeProvince: 'TT', homeRegion: 'Regione Test', createdAt: '2026-11-01T08:00:00.000Z'
  };
});
const facilities = ['A', 'B', 'C', 'D', 'HOSPICE'].map((suffix, i) => ({
  id: `TEST-FAC-${suffix}`, name: suffix === 'HOSPICE' ? 'Hospice Sintetico' : `Struttura Sintetica ${suffix}`,
  city: 'Citta Test', province: 'TT', region: 'Regione Test', kind: suffix === 'HOSPICE' ? 'Hospice' : 'Test',
  lat: 45.0 + i * 0.01, lon: 10.0 + i * 0.01, active: true,
  locationPrecision: 'city-centroid', aliasesLegacy: [], aliases: [],
  services: suffix === 'HOSPICE' ? ['HOSPICE'] : ['COD56_ALTRO', 'ODC']
}));
const config = {
  settings: [
    { id: 'COD56_ALTRO', code: '56', label: 'Riabilitazione sintetica', subtype: 'Test', display: 'Codice 56 · Riabilitazione sintetica' },
    { id: 'ODC', code: '', label: 'Ospedale di Comunità', subtype: '', display: 'OdC sintetico' },
    { id: 'HOSPICE', code: '', label: 'Hospice', subtype: '', display: 'Hospice sintetico' },
    { id: 'ALTRO', code: '', label: 'Altro', subtype: '', display: 'Altro sintetico' }
  ],
  wards: [
    { id: 'TEST-WARD-MED', label: 'Reparto Test Medicina', legacyAliases: [], active: true },
    { id: 'TEST-WARD-NEURO', label: 'Reparto Test Neurologia', legacyAliases: [], active: true }
  ],
  odcUnits: [{ id: 'TEST-ODC', name: 'Ospedale di Comunità Sintetico', city: 'Citta Test', province: 'TT', region: 'Regione Test', bedsAuthorized: 12, bedsOperational: 10, active: true }],
  facilities, contactHubs: [], municipalitySource: 'Fixture sintetica', sourceStats: {}
};
const episodes = patients.slice(0, 6).map((p, i) => ({
  id: `TEST-EP-${String(i + 1).padStart(2, '0')}`, patientId: p.id,
  admittedAt: '2026-10-20', status: 'OPEN', currentMacro: 'ASST', currentSite: i % 2 ? 'PO' : 'CR',
  currentWardId: i % 2 ? 'TEST-WARD-NEURO' : 'TEST-WARD-MED',
  currentWardLabel: i % 2 ? 'Reparto Test Neurologia' : 'Reparto Test Medicina',
  wardEnteredAt: '2026-10-27', wardHistory: [{ id: `TEST-WLOC-${i + 1}`, enteredAt: '2026-10-20', exitedAt: '',
    macro: 'ASST', site: i % 2 ? 'PO' : 'CR', ward: i % 2 ? 'Reparto Test Neurologia' : 'Reparto Test Medicina', provenance: 'synthetic_fixture' }]
}));
const pathways = [
  { id: 'TEST-PATH-01A', patientId: patients[0].id, hospitalEpisodeId: episodes[0].id, status: 'OPEN', target: 'EXTERNAL', requestedAt: '2026-11-01', requestedSettingId: 'COD56_ALTRO', originMacro: 'ASST', originSite: 'CR', originWard: 'Reparto Test Medicina', documentationComplete: 'YES', fktRequired: 'YES', fktStatus: 'IN_CORSO', priamoRequired: 'YES', priamoStatus: 'VALID', priamoExpiresAt: '2026-12-31', stableAtRequest: 'YES', dischargeabilityStatus: 'YES', dischargeableAt: '2026-11-02', otherCotInvolved: 'NO', requestReason: 'Fixture sintetica', cotConsultationId: 'TEST-COT-01' },
  { id: 'TEST-PATH-01B', patientId: patients[0].id, hospitalEpisodeId: episodes[0].id, status: 'OPEN', target: 'EXTERNAL', requestedAt: '2026-11-02', requestedSettingId: 'COD56_ALTRO', originMacro: 'ASST', originSite: 'CR', originWard: 'Reparto Test Medicina', documentationComplete: 'NO', fktRequired: 'NO', priamoRequired: 'NA', stableAtRequest: 'YES', dischargeabilityStatus: 'PENDING', otherCotInvolved: 'NO', requestReason: 'Secondo percorso sintetico' },
  { id: 'TEST-PATH-02', patientId: patients[1].id, hospitalEpisodeId: episodes[1].id, status: 'OPEN', target: 'ODC', requestedAt: '2026-11-03', requestedSettingId: 'ODC', originMacro: 'ASST', originSite: 'PO', originWard: 'Reparto Test Neurologia', documentationComplete: 'YES', fktRequired: 'YES', fktStatus: 'DA DEFINIRE', priamoRequired: 'NO', stableAtRequest: 'YES', dischargeabilityStatus: 'YES', otherCotInvolved: 'NO' },
  { id: 'TEST-PATH-03', patientId: patients[2].id, hospitalEpisodeId: episodes[2].id, status: 'OPEN', target: 'ODC', requestedAt: '2026-11-04', requestedSettingId: 'ODC', originMacro: 'ASST', originSite: 'CR', originWard: 'Reparto Test Medicina', documentationComplete: 'YES', fktRequired: 'NO', priamoRequired: 'NO', stableAtRequest: 'YES', dischargeabilityStatus: 'YES', otherCotInvolved: 'NO' },
  { id: 'TEST-PATH-04', patientId: patients[3].id, hospitalEpisodeId: episodes[3].id, status: 'OPEN', target: 'HOSPICE', requestedAt: '2026-11-05', requestedSettingId: 'HOSPICE', originMacro: 'ASST', originSite: 'PO', originWard: 'Reparto Test Neurologia', documentationComplete: 'NO', fktRequired: 'NO', priamoRequired: 'NA', hospiceArea: 'CREMONA', hospiceFacilityId: 'TEST-FAC-HOSPICE', hospiceConsultationAt: '2026-11-05', hospiceEligibility: 'YES', hospiceDocumentationAt: '2026-11-06', hospiceOutcome: 'PENDING' },
  { id: 'TEST-PATH-05', patientId: patients[4].id, hospitalEpisodeId: episodes[4].id, status: 'CLOSED', target: 'HOME', requestedAt: '2026-10-20', outcomeAt: '2026-11-07', finalDestination: 'Domicilio / servizi', requestedSettingId: 'ALTRO', originMacro: 'ASST', originSite: 'CR', originWard: 'Reparto Test Medicina', documentationComplete: 'YES', fktRequired: 'NO', priamoRequired: 'NO', closureReason: 'Chiusura sintetica' }
];
const contacts = [
  ['TEST-FC-01A', pathways[0], facilities[0], 'In attesa', '2026-11-08'],
  ['TEST-FC-01B', pathways[0], facilities[1], 'Nessun riscontro', ''],
  ['TEST-FC-01C', pathways[0], facilities[2], 'In attesa', '2026-11-09'],
  ['TEST-FC-01D', pathways[1], facilities[3], 'In attesa', '2026-11-10'],
  ['TEST-FC-02A', pathways[2], facilities[0], 'In attesa', '2026-11-11']
].map(([id, p, f, outcome, sentAt]) => ({
  id, patientId: p.patientId, pathwayId: p.id, facilityId: f.id, facilityNameAtContact: f.name,
  method: 'Email PEC', methods: ['Email PEC'], otherMethod: '', sentAt, responseAt: outcome === 'Nessun riscontro' ? '' : '', outcome,
  reason: '', createdAt: `${sentAt}T08:00:00.000Z`
}));
const cotConsultations = [
  { id: 'TEST-COT-01', patientId: patients[0].id, hospitalEpisodeId: episodes[0].id, pathwayId: pathways[0].id,
    requestedAt: '2026-11-01', responseAt: '2026-11-01', responseStatus: 'YES', appropriateness: 'YES', status: 'CLOSED', requester: 'TEST' },
  { id: 'TEST-COT-02', patientId: patients[1].id, hospitalEpisodeId: episodes[1].id, requestedAt: '2026-11-03',
    responseStatus: 'PENDING', appropriateness: '', status: 'OPEN', requester: 'TEST' }
];
const events = [
  ...patients.slice(0, 5).map((p, i) => ({ id: `TEST-EV-PAT-${i + 1}`, type: 'PATIENT_CREATED', patientId: p.id, refType: 'patient', refId: p.id, at: `2026-10-${String(20 + i).padStart(2, '0')}T08:00:00.000Z`, label: 'Paziente sintetico inserito', meta: { synthetic: true } })),
  { id: 'TEST-EV-WARD', type: 'WARD_TRANSFER', patientId: patients[0].id, refType: 'hospitalEpisode', refId: episodes[0].id, at: '2026-10-27T08:00:00.000Z', label: 'Trasferimento sintetico di reparto', meta: { synthetic: true } },
  { id: 'TEST-EV-PRIAMO', type: 'PRIAMO_UPDATED', patientId: patients[0].id, refType: 'dischargePathway', refId: pathways[0].id, at: '2026-11-03T08:00:00.000Z', label: 'PRIAMO sintetico aggiornato', meta: { synthetic: true } },
  { id: 'TEST-EV-FKT', type: 'FKT_UPDATED', patientId: patients[0].id, refType: 'dischargePathway', refId: pathways[0].id, at: '2026-11-04T08:00:00.000Z', label: 'FKT sintetica aggiornata', meta: { synthetic: true } }
];
const payload = {
  version: 3, meta: { schema: 'COT_ODC_FLOW_V3_2', createdAt: '2026-11-17T08:00:00.000Z', updatedAt: '2026-11-17T08:00:00.000Z' },
  config, patients, hospitalEpisodes: episodes, cotConsultations, dischargePathways: pathways,
  odcWaitingList: [{ id: 'TEST-WAIT-01', pathwayId: pathways[2].id, patientId: patients[1].id, odcUnitId: 'TEST-ODC', enteredAt: '2026-11-06', plannedAdmissionAt: '2026-11-20', status: 'PLANNED', closedAt: '' }],
  odcStays: [{ id: 'TEST-STAY-01', pathwayId: pathways[3].id, patientId: patients[2].id, odcUnitId: 'TEST-ODC', admittedAt: '2026-11-08', plannedDischargeAt: '2026-11-21', dischargeable: false, plannedDestination: 'Destinazione sintetica', dischargedAt: '', finalDestination: '' }],
  odcAssessments: [{ id: 'TEST-ASSESS-01', stayId: 'TEST-STAY-01', patientId: patients[2].id, scale: 'ICA', phase: 'INGRESSO', assessedAt: '2026-11-08', score: 4, assessor: 'TEST' }],
  facilityContacts: contacts, events, audit: [], revisions: [], cotCases: [], cotCaseLinks: [], cotCaseReconciliation: []
};

function extractFunction(name, nextName) {
  const start = source.indexOf(`async function ${name}(`);
  const end = source.indexOf(`async function ${nextName}(`, start + 1);
  if (start < 0 || end < 0) throw new Error(`R8 function ${name} not found`);
  return source.slice(start, end).trim();
}
const cryptoConstants = {
  ARCHIVE_FORMAT: 'COT_PERCORSI_ENCRYPTED_JSON', ARCHIVE_VERSION: 2,
  ARCHIVE_AAD: 'COT_PERCORSI_V1', PBKDF2_ITERATIONS: 250000,
  COT_V3_SCHEMA: 'COT_ODC_FLOW_V3_2'
};
const collections = ['patients','hospitalEpisodes','cotConsultations','dischargePathways','odcWaitingList','odcStays','odcAssessments','facilityContacts','events','audit','revisions','cotCases','cotCaseLinks','cotCaseReconciliation'];
function payloadCompatibilityError(value) {
  if (value.version !== 3 || value.meta?.schema !== cryptoConstants.COT_V3_SCHEMA || !value.config || collections.some(k => !Array.isArray(value[k]))) return 'Fixture schema mismatch';
  return '';
}
const helpers = `
const ARCHIVE_FORMAT=${JSON.stringify(cryptoConstants.ARCHIVE_FORMAT)};
const ARCHIVE_VERSION=${cryptoConstants.ARCHIVE_VERSION};
const ARCHIVE_AAD=${JSON.stringify(cryptoConstants.ARCHIVE_AAD)};
const PBKDF2_ITERATIONS=${cryptoConstants.PBKDF2_ITERATIONS};
const COT_V3_SCHEMA=${JSON.stringify(cryptoConstants.COT_V3_SCHEMA)};
async function deriveKey(password,salt,usages,it=PBKDF2_ITERATIONS){const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:it,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,usages)}
function bytesToB64(bytes){let bin='';for(let i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin)}
function payloadCompatibilityError(x){if(x.version!==3||x.meta?.schema!==COT_V3_SCHEMA||!x.config||${JSON.stringify(collections)}.some(k=>!Array.isArray(x[k])))return 'Fixture schema mismatch';return ''}
`;
const context = vm.createContext({ crypto: webcrypto, TextEncoder, Uint8Array, btoa: value => Buffer.from(value, 'binary').toString('base64') });
vm.runInContext(helpers + extractFunction('encryptArchive', 'decryptArchive') + '\nglobalThis.r8EncryptArchive=encryptArchive;', context);
const password = randomBytes(24).toString('base64url');
const envelope = await context.r8EncryptArchive(payload, password);
const path = join(tmpdir(), `cot-r8-synthetic-${process.pid}.json`);
await writeFile(path, JSON.stringify(envelope, null, 2), { mode: 0o600, flag: 'wx' });
console.log(JSON.stringify({ path, password, counts: { patients: patients.length, pathways: pathways.length, requests: contacts.length, events: events.length, odcStays: payload.odcStays.length, hospice: pathways.filter(p => p.target === 'HOSPICE').length } }));
