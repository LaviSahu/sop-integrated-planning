// Golden-gate identity check: JS port fed the embedded DATA must reproduce
// the golden fixture's scenario outputs to 1e-9. Run by tests/test_js_port.py.
const fs = require('fs');
const engine = require(process.env.ENGINE);

const html = fs.readFileSync(process.env.DASHBOARD, 'utf8');
const i = html.indexOf('<script>const DATA = ');
const j = html.indexOf('</script>', i);
const D = JSON.parse(html.slice(i + '<script>const DATA = '.length, j).replace(/;\s*$/, ''));

const txt = fs.readFileSync(process.env.GOLDEN, 'utf8');
const GOLD = JSON.parse(txt.replace(/^.*?window\.SOP_DATA = /s, '').replace(/;\s*$/, ''));

const levers = {
  volMult: 0, seasonShift: 0, hours: {}, familyUplift: {},
  priceDeltaPct: {}, vcDeltaPct: {}, openingDeltaPct: {},
  rationRule: 'throughput-per-constraint'
};
let mismatches = 0;
const num = (a, b) => typeof a === 'number' && Math.abs(a - b) > 1e-9;

['base', 'upside', 'constrained'].forEach(tag => {
  const res = engine.recomputeScenario(D, levers, tag);
  const scen = res.scenario;
  const golden = GOLD.scenarios[tag];

  Object.keys(golden.summary).forEach(k => {
    if (num(golden.summary[k], scen.summary[k])) {
      console.log('SUMMARY', tag, k, scen.summary[k], golden.summary[k]);
      mismatches++;
    }
  });
  golden.monthly.forEach((g, mi) => {
    Object.keys(g).forEach(k => {
      if (num(g[k], scen.monthly[mi][k])) {
        console.log('MONTHLY', tag, mi, k, scen.monthly[mi][k], g[k]);
        mismatches++;
      }
    });
  });
  Object.keys(golden.utilization).forEach(rid => {
    golden.utilization[rid].forEach((g, ui) => {
      Object.keys(g).forEach(k => {
        if (num(g[k], scen.utilization[rid][ui][k])) {
          console.log('UTIL', tag, rid, ui, k, scen.utilization[rid][ui][k], g[k]);
          mismatches++;
        }
      });
    });
  });
  golden.reconciliation.forEach((g, ri) => {
    Object.keys(g).forEach(k => {
      if (num(g[k], scen.reconciliation[ri][k])) {
        console.log('RECON', tag, ri, k, scen.reconciliation[ri][k], g[k]);
        mismatches++;
      }
    });
  });
  Object.keys(GOLD.provenance[tag]).forEach(fid => {
    Object.keys(GOLD.provenance[tag][fid]).forEach(mk => {
      const gp = GOLD.provenance[tag][fid][mk];
      const jp = res.provenance[fid][mk];
      ['supply', 'financials'].forEach(sect => {
        Object.keys(gp[sect]).forEach(k => {
          if (num(gp[sect][k], jp[sect][k])) {
            console.log('PROV', tag, fid, mk, sect, k, jp[sect][k], gp[sect][k]);
            mismatches++;
          }
        });
      });
    });
  });
});

console.log('MISMATCHES=' + mismatches);
if (mismatches) process.exit(1);
