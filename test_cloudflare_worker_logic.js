/**
 * Unit & Simulated Integration Tests for Cash Advance (Local Travel) Watchdog
 * Run with: node test_cloudflare_worker_logic.js
 */

import worker, {
  ALL_9_STAGES,
  NODE_ID_TO_STAGE,
  VENDOR_BILL_WIDGET_ID,
  CHECK_NO_WIDGET_ID,
  MAX_SUBREQUESTS,
  extractText,
  extractUrlField,
  normalizeUserField,
  decodeInstanceCode,
  formatTimestamp,
  formatDuration,
  normalizeStageName,
  normalizeStageAction,
  extractLinkedCashAdvanceRequestNos,
  buildFiledLiquidationRequestSet,
  computeOverallStatus,
  extractStageMetrics,
  extractFinancialFields,
  diffTable2Fields,
  isSettledTerminalRow,
  runAutoHealingCycle,
  resetTokenCache,
} from './cloudflare_worker.js';

let passed = 0;
let failed = 0;

function assertEq(actual, expected, label) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    passed++;
  } else {
    failed++;
    console.error(`[FAIL] ${label}\n  Expected: ${e}\n  Actual  : ${a}`);
  }
}

function assertTrue(cond, label) {
  if (cond) {
    passed++;
  } else {
    failed++;
    console.error(`[FAIL] ${label}`);
  }
}

// 1. Canonical Constants
assertEq(ALL_9_STAGES.length, 9, 'ALL_9_STAGES has 9 stages');
assertEq(Object.keys(NODE_ID_TO_STAGE).length, 9, 'NODE_ID_TO_STAGE has 9 node mappings');
assertEq(NODE_ID_TO_STAGE['fb1f0c3e7fe4f2f0ea3f2b8a6e54704b'], 'Booking of Hotel', 'Flight-branch hotel node_id maps to Booking of Hotel');
assertEq(NODE_ID_TO_STAGE['57f6a1eaf7360efadac5a69066df327e'], 'Booking of Hotel (No Flight)', 'No-flight hotel node_id maps to Booking of Hotel (No Flight)');
assertEq(VENDOR_BILL_WIDGET_ID, 'widget17501233698840001', 'Vendor Bill widget ID');
assertEq(CHECK_NO_WIDGET_ID, 'widget17501234330640001', 'Check No widget ID');
assertEq(MAX_SUBREQUESTS, 42, 'MAX_SUBREQUESTS budget guard');

// 2. SourceID Decoding
const sampleSourceId = Buffer.from(
  '7709735905409388300:629354AA-529A-4A0E-93C9-9A009C9EEE61:830189cf4e68cda16654f9df3ac53ed2:1'
).toString('base64');
assertEq(decodeInstanceCode(sampleSourceId), '629354AA-529A-4A0E-93C9-9A009C9EEE61', 'Decodes Base64 SourceID');
assertEq(decodeInstanceCode([{ text: sampleSourceId }]), '629354AA-529A-4A0E-93C9-9A009C9EEE61', 'Decodes Bitable rich-text SourceID');
assertEq(decodeInstanceCode(''), null, 'Empty SourceID returns null');

// 3. Field Normalization
assertEq(extractText([{ text: ' VB-100 ' }]), 'VB-100', 'extractText handles rich text array');
assertEq(extractUrlField([{ text: '202609140041', link: 'https://example.com' }]), { text: '202609140041', link: 'https://example.com' }, 'extractUrlField extracts link/text');
assertEq(normalizeUserField([{ id: 'ou_abc', name: 'Mark' }]), [{ id: 'ou_abc' }], 'normalizeUserField strips enriched fields');
assertEq(normalizeUserField(null, 'ou_fallback'), [{ id: 'ou_fallback' }], 'normalizeUserField uses fallback');

// 4. Formatting Helpers
assertEq(formatTimestamp(1700000000000), '2023-11-15 06:13:20', 'formatTimestamp UTC+8');
assertEq(formatDuration(1000, 31000), '< 1 min', 'formatDuration < 1 min');
assertEq(formatDuration(0, 120000), '', 'formatDuration zero start');
assertEq(formatDuration(1000, 601000), '10 min', 'formatDuration minutes');

// 5. Stage Name & Action Normalization
assertEq(normalizeStageAction('PENDING'), 'PENDING', 'normalizeStageAction keeps PENDING');
assertEq(normalizeStageAction('APPROVED'), 'APPROVED', 'normalizeStageAction keeps APPROVED');
assertEq(normalizeStageAction('DONE'), 'APPROVED', 'normalizeStageAction maps DONE to APPROVED');
assertEq(normalizeStageAction('AUTO-PASSED'), 'APPROVED', 'normalizeStageAction maps AUTO-PASSED to APPROVED');
assertEq(normalizeStageAction('REJECTED'), 'REJECTED', 'normalizeStageAction keeps REJECTED');
assertEq(normalizeStageAction('CANCELED'), 'REJECTED', 'normalizeStageAction maps CANCELED to REJECTED');

// 5b. Cross-Base Liquidation Matching
assertEq(
  extractLinkedCashAdvanceRequestNos('202610090038-Ian Mojica-Cash Advance Form - Travelling Expenses (Local)-2026-10-09'),
  ['202610090038'],
  'extractLinkedCashAdvanceRequestNos extracts 12-digit CA Request No.'
);
const filedSet = buildFiledLiquidationRequestSet([
  { fields: { Status: 'Approved', 'Link Approved Cash advance': '202610090023-Enrico-CA' } },
  { fields: { Status: 'Under Review', 'Link Approved Cash advance': '202610090038-Ian-CA' } },
  { fields: { Status: 'Recalled', 'Link Approved Cash advance': '202610090099-Recalled-CA' } },
  { fields: { Status: 'Rejected', 'Link Approved Cash advance': '202610090088-Rejected-CA' } },
]);
assertTrue(filedSet.has('202610090023'), 'Approved liquidation marks CA as filed (Yes)');
assertTrue(filedSet.has('202610090038'), 'Under Review liquidation marks CA as filed (Yes)');
assertTrue(!filedSet.has('202610090099'), 'Recalled liquidation does NOT mark CA as filed (No Record)');
assertTrue(!filedSet.has('202610090088'), 'Rejected liquidation does NOT mark CA as filed (No Record)');
assertEq(normalizeStageName('Direct Supervisor'), 'Direct Supervisor (if none, enter requester name)', 'Normalize Direct Supervisor');
assertEq(normalizeStageName('Team Head'), 'Team Head (if none, enter requester name)', 'Normalize Team Head');
assertEq(normalizeStageName('Booking of Hotel (No Flight)'), 'Booking of Hotel (No Flight)', 'Normalize Booking of Hotel (No Flight)');
assertEq(normalizeStageName('Booking of Flight'), 'Booking of Flight', 'Normalize Booking of Flight');

// 6. Overall Status Progression
assertEq(computeOverallStatus('APPROVED', {}), 'COMPLETED: Cash Advance Released', 'APPROVED status');
assertEq(computeOverallStatus('REJECTED', {}), 'Rejected', 'REJECTED status');
assertEq(computeOverallStatus('CANCELED', {}), 'Recalled', 'CANCELED -> Recalled');
assertEq(computeOverallStatus('DELETED', {}), 'Canceled', 'DELETED -> Canceled');
assertEq(computeOverallStatus('PENDING', { 'Direct Supervisor (if none, enter requester name) Action': 'PENDING' }), 'Phase 1: Line & Dept Review', 'Phase 1');
assertEq(computeOverallStatus('PENDING', { 'Accounting Processing Action': 'PENDING' }), 'Phase 2: Accounting Processing', 'Phase 2');
assertEq(computeOverallStatus('PENDING', { 'Accounting Processing Action': 'APPROVED', 'Booking of Flight Action': 'PENDING' }), 'Phase 3: Travel Booking', 'Phase 3 (Flight)');
assertEq(computeOverallStatus('PENDING', { 'Accounting Processing Action': 'APPROVED', 'Booking of Hotel (No Flight) Action': 'PENDING' }), 'Phase 3: Travel Booking', 'Phase 3 (Hotel No Flight)');
assertEq(computeOverallStatus('PENDING', { 'Booking of Hotel Action': 'APPROVED', 'Treasury Processing Action': 'PENDING' }), 'Phase 4: Treasury Processing & Check Release', 'Phase 4 (Treasury)');
assertEq(computeOverallStatus('PENDING', { 'For Check Releasing Action': 'PENDING' }), 'Phase 4: Treasury Processing & Check Release', 'Phase 4 (Check Releasing)');

// 7. Extract Stage Metrics (Flight vs No-Flight Hotel Disambiguation)
const flightInst = {
  task_list: [
    { node_id: 'cdab9cee83f7969bc24bfcdcdd33e8aa', node_name: 'Direct Supervisor', open_id: 'ou_1', start_time: '1700000000000', end_time: '1700000060000', status: 'APPROVED' },
    { node_id: '9fb7bf6d70a142917e3a01c4ba4db848', node_name: 'Booking of Flight', open_id: 'ou_2', start_time: '1700000100000', end_time: '1700000200000', status: 'APPROVED' },
    { node_id: 'fb1f0c3e7fe4f2f0ea3f2b8a6e54704b', node_name: 'Booking of Hotel', open_id: 'ou_3', start_time: '1700000200000', end_time: '1700000300000', status: 'APPROVED' },
  ],
};
const flightMetrics = extractStageMetrics(flightInst);
assertEq(flightMetrics['Direct Supervisor (if none, enter requester name) Action'], 'APPROVED', 'Flight inst Direct Supervisor');
assertEq(flightMetrics['Booking of Flight Action'], 'APPROVED', 'Flight inst Booking of Flight');
assertEq(flightMetrics['Booking of Hotel Action'], 'APPROVED', 'Flight inst Booking of Hotel');
assertEq(flightMetrics['Booking of Hotel (No Flight) Action'], undefined, 'Flight inst does not populate No Flight hotel');

const noFlightInst = {
  task_list: [
    { node_id: '57f6a1eaf7360efadac5a69066df327e', node_name: 'Booking of Hotel', open_id: 'ou_4', start_time: '1700000400000', end_time: '1700000500000', status: 'PENDING' },
  ],
};
const noFlightMetrics = extractStageMetrics(noFlightInst);
assertEq(noFlightMetrics['Booking of Hotel (No Flight) Action'], 'PENDING', 'No-Flight inst populates Booking of Hotel (No Flight)');
assertEq(noFlightMetrics['Booking of Hotel Action'], undefined, 'No-Flight inst does not populate flight Booking of Hotel');

// 8. Financial Fields Extraction
const formStr = JSON.stringify([
  { id: 'widget17501233698840001', name: 'Vendor Bill No.', value: 'VB-2026-001' },
  { id: 'widget17501234330640001', name: 'Check No.', value: 'CHK-998877' },
]);
assertEq(extractFinancialFields(formStr), { vendorBillNo: 'VB-2026-001', checkNo: 'CHK-998877' }, 'extractFinancialFields extracts VB & Check');

// 9. Type-Aware Diff Engine
const existingT2Fields = {
  'Overall Status': 'Phase 3: Travel Booking',
  Requester: [{ id: 'ou_req', name: 'Mark', en_name: 'Mark' }],
  'Task ID': { text: '202609140041', link: 'https://applink.larksuite.com/x' },
  'Booking of Flight Start': 1700000100000,
};
const targetSame = {
  'Overall Status': 'Phase 3: Travel Booking',
  Requester: [{ id: 'ou_req' }],
  'Task ID': { text: '202609140041', link: 'https://applink.larksuite.com/x' },
  'Booking of Flight Start': 1700000100000,
};
assertEq(diffTable2Fields(existingT2Fields, targetSame), {}, 'No diff when normalized values match');
assertEq(
  diffTable2Fields(existingT2Fields, { ...targetSame, 'Overall Status': 'Phase 4: Treasury Processing & Check Release' }),
  { 'Overall Status': 'Phase 4: Treasury Processing & Check Release' },
  'Detects Overall Status diff'
);

// 10. Settled Terminal Row Check
assertTrue(
  isSettledTerminalRow(
    { Status: 'Approved', 'Vendor Bill No.': 'VB-1', 'Check No.': 'CHK-1', 'Request No.': { text: '1', link: 'https://a' }, Requester: [{ id: 'ou_1' }] },
    { fields: { 'Overall Status': 'COMPLETED: Cash Advance Released', 'Task ID': { text: '1', link: 'https://a' }, Requester: [{ id: 'ou_1' }] } }
  ),
  'Settled APPROVED row with VB & Check is skipped'
);
assertTrue(
  !isSettledTerminalRow(
    { Status: 'Approved', 'Vendor Bill No.': '', 'Check No.': '' },
    { fields: { 'Overall Status': 'COMPLETED: Cash Advance Released' } }
  ),
  'APPROVED row missing VB/Check is not yet settled'
);

// 11. Simulated Integration Test (Mocked fetch + /health + /sync)
async function runIntegrationTests() {
  resetTokenCache();
  const originalFetch = globalThis.fetch;
  const calls = [];

  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url, method: opts.method || 'GET', body: opts.body ? JSON.parse(opts.body) : null });
    if (url.includes('tenant_access_token')) {
      return new Response(JSON.stringify({ code: 0, tenant_access_token: 'tok_test', expire: 7200 }));
    }
    if (url.includes('/tables/tblMain/records') && (!opts.method || opts.method === 'GET')) {
      return new Response(
        JSON.stringify({
          code: 0,
          data: {
            has_more: false,
            items: [
              {
                record_id: 'rec_t1_1',
                fields: {
                  SourceID: sampleSourceId,
                  'Request No.': { text: '202609140041', link: 'https://applink.larksuite.com/test' },
                  Status: 'Approved',
                  Requester: [{ id: 'ou_req_1' }],
                  'Vendor Bill No.': '',
                  'Check No.': '',
                },
              },
            ],
          },
        })
      );
    }
    if (url.includes('/tables/tblLog/records') && (!opts.method || opts.method === 'GET')) {
      return new Response(JSON.stringify({ code: 0, data: { has_more: false, items: [] } }));
    }
    if (url.includes('/approval/v4/instances/629354AA-529A-4A0E-93C9-9A009C9EEE61')) {
      return new Response(
        JSON.stringify({
          code: 0,
          data: {
            status: 'APPROVED',
            open_id: 'ou_req_1',
            serial_number: '202609140041',
            form: formStr,
            task_list: flightInst.task_list,
          },
        })
      );
    }
    if (url.includes('/tables/tblMain/records/rec_t1_1') && opts.method === 'PUT') {
      return new Response(JSON.stringify({ code: 0, data: {} }));
    }
    if (url.includes('/tables/tblLog/records') && opts.method === 'POST') {
      return new Response(JSON.stringify({ code: 0, data: { record: { record_id: 'rec_t2_1', fields: {} } } }));
    }
    return new Response(JSON.stringify({ code: 404 }), { status: 404 });
  };

  try {
    const env = {
      LARK_APP_ID: 'cli_aa75292d72b8df08',
      LARK_APP_SECRET: 'test_secret',
      LARK_BASE_TOKEN: 'ExBjbp1ORa1bSDst0NOlcJMOgRc',
      LARK_MAIN_TABLE_ID: 'tblMain',
      LARK_LOG_TABLE_ID: 'tblLog',
    };

    const res = await runAutoHealingCycle(env);
    assertEq(res.healedCount, 1, 'Integration: created 1 Table 2 record');
    assertEq(res.table1HealedCount, 1, 'Integration: auto-healed Table 1 VB & Check No.');

    const t1Put = calls.find((c) => c.method === 'PUT' && c.url.includes('tblMain'));
    assertEq(t1Put.body.fields, { 'Vendor Bill No.': 'VB-2026-001', 'Check No.': 'CHK-998877' }, 'Integration: Table 1 PUT payload');

    const t2Post = calls.find((c) => c.method === 'POST' && c.url.includes('tblLog'));
    assertEq(t2Post.body.fields['Overall Status'], 'COMPLETED: Cash Advance Released', 'Integration: Table 2 Overall Status');
    assertEq(t2Post.body.fields['Booking of Flight Action'], 'APPROVED', 'Integration: Table 2 Flight stage');
    assertEq(t2Post.body.fields['Booking of Hotel Action'], 'APPROVED', 'Integration: Table 2 Hotel stage');
    assertEq(t2Post.body.fields['SourceID'], sampleSourceId, 'Integration: Table 2 SourceID');

    const healthRes = await worker.fetch(new Request('https://example.com/health'), env, null);
    const healthJson = await healthRes.json();
    assertEq(healthRes.status, 200, 'Health endpoint HTTP 200');
    assertEq(healthJson.service, 'cash-advance-local-travel', 'Health service name');

    const waitUntilPromises = [];
    const syncRes = await worker.fetch(new Request('https://example.com/sync'), env, {
      waitUntil: (p) => waitUntilPromises.push(p),
    });
    assertEq(syncRes.status, 200, 'Sync endpoint HTTP 200');
    await Promise.all(waitUntilPromises);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

await runIntegrationTests();

console.log(`\nVerification Complete: ${passed}/${passed + failed} Tests Passed`);
if (failed > 0) {
  process.exit(1);
}
