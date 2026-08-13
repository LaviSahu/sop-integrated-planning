// Lever-mutation gate: JS port with the representative lever overrides must
// reproduce the Python engine run with the SAME overrides. Reads the Python
// truth from process.env.PY_MUTATED.
const fs = require('fs');
const engine = require(process.env.ENGINE);

const html = fs.readFileSync(process.env.DASHBOARD, 'utf8');
const i = html.indexOf('<script>const DATA = ');
const j = html.indexOf('</script>', i);
const D = JSON.parse(html.slice(i + '<script>const DATA = '.length, j).replace(/;\s*$/, ''));

const resId = D.resources.find(r => r.id === 'RES-LINEA');
const levers = {
  volMult: 10,
  seasonShift: 0,
  rationRule: 'throughput-per-constraint',
  hours: { 'RES-LINEA': resId.monthly_available_hours * 1.05 },
  familyUplift: {},
  priceDeltaPct: { 'FAM-DRY': 10 },
  vcDeltaPct: { 'FAM-DRY': -3 },
  openingDeltaPct: {}
};

const res = engine.recomputeScenario(D, levers, 'constrained');
const scen = res.scenario;
const PY = JSON.parse(fs.readFileSync(process.env.PY_MUTATED, 'utf8'));

let mismatches = 0;
const num = (a, b) => typeof a === 'number' && Math.abs(a - b) > 1e-9;

Object.keys(PY.summary).forEach(k => {
  if (num(PY.summary[k], scen.summary[k])) {
    console.log('SUMMARY', k, scen.summary[k], PY.summary[k]);
    mismatches++;
  }
});
PY.monthly.forEach((g, mi) => {
  Object.keys(g).forEach(k => {
    if (num(g[k], scen.monthly[mi][k])) {
      console.log('MONTHLY', mi, k, scen.monthly[mi][k], g[k]);
      mismatches++;
    }
  });
});
PY.reconciliation.forEach((g, ri) => {
  Object.keys(g).forEach(k => {
    if (num(g[k], scen.reconciliation[ri][k])) {
      console.log('RECON', ri, k, scen.reconciliation[ri][k], g[k]);
      mismatches++;
    }
  });
});
Object.keys(PY.utilization).forEach(rid => {
  PY.utilization[rid].forEach((g, ui) => {
    Object.keys(g).forEach(k => {
      if (num(g[k], scen.utilization[rid][ui][k])) {
        console.log('UTIL', rid, ui, k, scen.utilization[rid][ui][k], g[k]);
        mismatches++;
      }
    });
  });
});

console.log('MISMATCHES=' + mismatches);
if (mismatches) process.exit(1);
