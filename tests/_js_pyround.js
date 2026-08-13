// pyRound gate: JS banker's rounding must equal Python round() on the
// known-divergent float cases. Truth table injected via process.env.TRUTH.
const engine = require(process.env.ENGINE);
const truth = JSON.parse(process.env.TRUTH);

const cases = JSON.parse(process.env.CASES);
let bad = 0;
cases.forEach(([x, dp], idx) => {
  const got = engine.pyRound(x, dp);
  const exp = truth[idx];
  if (Math.abs(got - exp) > 1e-9) {
    console.log('FAIL', x, dp, got, exp);
    bad++;
  }
});
console.log('BAD=' + bad);
if (bad) process.exit(1);
