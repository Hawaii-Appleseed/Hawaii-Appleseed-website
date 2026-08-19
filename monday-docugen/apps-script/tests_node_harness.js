// Stub the Apps Script globals so the pure logic in Code.gs can run under node.
global.Utilities = {
  // honour the format string the way Apps Script does, for the patterns we use
  formatDate: (d, tz, fmt) => {
    const pad = n => String(n).padStart(2, '0');
    const months = ['January','February','March','April','May','June','July',
                    'August','September','October','November','December'];
    if (fmt === 'MM/dd/yyyy') return `${pad(d.getMonth()+1)}/${pad(d.getDate())}/${d.getFullYear()}`;
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  },
};
global.Session = { getScriptTimeZone: () => 'Pacific/Honolulu' };
global.PropertiesService = { getScriptProperties: () => ({ getProperty: () => null, setProperty: () => {} }) };
global.Logger = { log: () => {} };
global.DriveApp = {}; global.DocumentApp = {}; global.UrlFetchApp = {}; global.ContentService = {};

const fs = require('fs');
const src = fs.readFileSync(process.env.HOME + '/monday-docugen/apps-script/Code.js', 'utf8');
eval(src);

const ctx = buildContext_(fixtureItem_());
const checks = [
  ['Total summed from corrected lines', ctx.fields.total === '193.19'],
  ['expense-only Amount = Expense Amt', ctx.lines[0].amount === '181.19'],
  ['mileage-only Amount = Miles x Rate', ctx.lines[1].amount === '12.00'],
  ['board_relation Budget Category', ctx.lines[0].budget_category === 'Meals & Entertainment'],
  ['ampersand survives coercion', ctx.lines[0].budget_category.includes('&')],
  ['blank dropdown -> empty string', ctx.lines[0].lobbying_fundraising === ''],
  ['dropdown label kept', ctx.lines[1].lobbying_fundraising === 'Lobbying Expense'],
  ['date is MM/DD/YYYY like DocuGen', ctx.fields.date_of_request === '08/15/2026'],
  ['files joined', ctx.fields.documentation === 'receipt.pdf, calendar.png'],
  ['two line items', ctx.lines.length === 2],
  ['numbers column plain, no $', ctx.lines[0].expense_amt === '181.19'],
  ['whole numbers stay whole (no .00)', ctx.lines[1].miles === '20'],
];

// The critical regression: blank Total must still sum the corrected line amounts.
const noTotal = JSON.parse(JSON.stringify(fixtureItem_()));
noTotal.column_values = noTotal.column_values.filter(c => c.column.title !== 'Total');
const fb = buildContext_(noTotal);
checks.push(['blank Total sums corrected amounts (was 0.00 before fix)', fb.fields.total === '193.19']);

// The bug this was all for: the board's own Amount formula is Expense Amt only, so a
// mileage-only line historically computed $0 - and so did any total built from it.
const mileageOnly = JSON.parse(JSON.stringify(fixtureItem_()));
mileageOnly.column_values = mileageOnly.column_values.filter(c => c.column.title !== 'Total');
mileageOnly.subitems = [{
  id: '9', name: 'Mileage only', column_values: [
    { id: 'numbers5__1', type: 'numbers', text: '24',
      column: { id: 'numbers5__1', title: 'Miles', type: 'numbers' } },
    { id: 'numbers75__1', type: 'numbers', text: '0.6',
      column: { id: 'numbers75__1', title: 'Mileage Rate', type: 'numbers' } },
    { id: 'formula_1__1', type: 'formula', text: null, display_value: '$0.00',
      column: { id: 'formula_1__1', title: 'Amount', type: 'formula' } },
  ],
}];
const mo = buildContext_(mileageOnly);
checks.push(['mileage-only line is not $0 (the original bug)', mo.lines[0].amount === '14.40']);
checks.push(['mileage-only Total is not $0', mo.fields.total === '14.40']);

let failed = 0;
for (const [name, ok] of checks) { if (!ok) failed++; console.log((ok ? 'PASS  ' : 'FAIL  ') + name); }
console.log(`\n${checks.length - failed}/${checks.length} passed`);
if (failed) { console.log('total was:', fb.fields.total); process.exit(1); }


// --- regression: a concatenated mirror Total must not reach the document ---
const concat = JSON.parse(JSON.stringify(fixtureItem_()));
concat.column_values = concat.column_values.map(c =>
  c.column.title === 'Total' ? { ...c, display_value: '18.50, 142.75' } : c);
const cc = buildContext_(concat);
const extra = [
  // The mirror's raw value is never read at all now - concatenated or not, its display_
  // value is ignored and the total always comes from the corrected lines. That mirror
  // can look like a plausible lone number for a mileage-only item while still being
  // wrong, so partially trusting it (the old grand_total heuristic) was never safe here.
  ['concatenated mirror Total is ignored, lines summed', cc.fields.total === '193.19'],
  ['a plausible-looking mirror value is still ignored',
   buildContext_(fixtureItem_()).fields.total === '193.19'],
  ['no $ leaks into the Amount column', !/\$/.test(cc.lines.map(l => l.amount).join(''))],
];
let f2 = 0;
for (const [n, ok] of extra) { if (!ok) f2++; console.log((ok ? 'PASS  ' : 'FAIL  ') + n); }
if (f2) { console.log('total was:', cc.fields.total, '| amounts:', cc.lines.map(l=>l.amount)); process.exit(1); }
console.log('DocuGen-format regressions covered');
