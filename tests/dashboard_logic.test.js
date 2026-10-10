// Checks that the numbers computed in the browser (dashboard/metrics.js on dashboard/data.js)
// match the KPI tables produced by the Gold layer (outputs/kpi_*.csv).
// Run: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const dataFile = path.join(root, 'dashboard', 'data.js');
const available = fs.existsSync(dataFile) && fs.existsSync(path.join(root, 'outputs', 'kpi_overview.csv'));

const readCsv = (name) => {
  const [head, ...lines] = fs.readFileSync(path.join(root, 'outputs', name), 'utf8').trim().split('\n');
  const cols = head.split(',');
  return lines.map((l) => Object.fromEntries(l.split(',').map((v, i) => [cols[i], v])));
};
const close = (a, b, tol = 1e-6, msg = '') =>
  assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${msg} ${a} vs ${b}`);

test('dashboard figures match the Gold KPI tables', { skip: !available && 'run the pipeline first' }, () => {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(dataFile, 'utf8'), sandbox);
  const data = sandbox.window.OLIST_DATA;
  const M = require(path.join(root, 'dashboard', 'metrics.js'));
  const ctx = M.prepare(data);
  const all = { m0: 0, m1: ctx.M - 1, state: -1, cat: -1 };

  // --- structure: items sorted by order index (needed by byCategory)
  for (let k = 1; k < ctx.K; k++) assert.ok(ctx.io[k] >= ctx.io[k - 1], 'items must be sorted by order');

  // --- overview
  const ov = readCsv('kpi_overview.csv')[0];
  const t = M.totals(ctx, M.select(ctx, all));
  close(t.revenue, +ov.total_revenue, 1e-9, 'revenue');
  assert.equal(t.orders, +ov.orders);
  assert.equal(t.customers, +ov.customers);
  close(t.aov, +ov.avg_order_value, 1e-9, 'aov');
  close(t.repeatRate, +ov.repeat_rate, 1e-9, 'repeat rate');
  close(t.avgDelivery, +ov.avg_delivery_days, 1e-9, 'delivery');
  close(t.lateRate, +ov.late_rate, 1e-9, 'late rate');
  close(t.avgReview, +ov.avg_review_score, 1e-9, 'review');

  // --- monthly
  const mon = M.monthly(ctx, M.select(ctx, all, { month: true }));
  for (const row of readCsv('kpi_monthly.csv')) {
    const m = mon.find((x) => x.month === row.year_month);
    assert.equal(m.orders, +row.orders, row.year_month);
    close(m.revenue, +row.revenue, 1e-9, row.year_month);
    close(m.avgReview, +row.avg_review_score, 1e-9, row.year_month);
  }

  // --- states (ignoring the state filter, like the chart does)
  const states = M.byState(ctx, M.select(ctx, all, { state: true }));
  for (const row of readCsv('kpi_state.csv')) {
    const s = states.find((x) => x.code === row.state);
    close(s.revenue, +row.revenue, 1e-9, row.state);
    assert.equal(s.orders, +row.orders);
    close(s.lateRate, +row.late_rate, 1e-9, row.state);
  }

  // --- categories
  const cats = M.byCategory(ctx, M.select(ctx, all, { cat: true }));
  for (const row of readCsv('kpi_category.csv')) {
    const c = cats.find((x) => x.name === row.category);
    close(c.revenue, +row.revenue, 1e-9, row.category);
    assert.equal(c.orders, +row.orders, row.category);
  }

  // --- delay vs rating
  const buckets = M.delayBuckets(ctx, M.select(ctx, all));
  for (const row of readCsv('kpi_delivery_review.csv')) {
    const b = buckets.find((x) => x.key === row.delay_bucket);
    assert.equal(b.orders, +row.orders, row.delay_bucket);
    close(b.avgReview, +row.avg_review_score, 1e-9, row.delay_bucket);
  }

  // --- filters: a state / category filter gives that row of the KPI tables
  const sp = M.totals(ctx, M.select(ctx, { ...all, state: data.states.findIndex((s) => s.code === 'SP') }));
  const spRow = readCsv('kpi_state.csv').find((r) => r.state === 'SP');
  close(sp.revenue, +spRow.revenue, 1e-9, 'SP revenue');
  assert.equal(sp.orders, +spRow.orders);

  const hb = M.totals(ctx, M.select(ctx, { ...all, cat: data.categories.indexOf('health_beauty') }));
  const hbRow = readCsv('kpi_category.csv').find((r) => r.category === 'health_beauty');
  close(hb.revenue, +hbRow.revenue, 1e-9, 'health_beauty revenue');
  assert.equal(hb.orders, +hbRow.orders);

  // --- presets stay inside the data
  for (const p of ['complete', 'all', 'y2017', 'y2018', 'last12']) {
    const [a, b] = M.presetRange(p, data);
    assert.ok(a >= 0 && b < ctx.M && a <= b, `preset ${p}: ${a}-${b}`);
  }
});
