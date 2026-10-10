/*
 * Dashboard logic without any DOM code: filters + KPI computation + number formatting.
 * Loaded by index.html in the browser, and by tests/dashboard_logic.test.js in Node,
 * so the figures shown on screen are checked against the Gold layer.
 *
 * Data model (see pipeline/dashboard_export.py):
 *   orders  columns, one entry per valid sale: m month, s state, u customer, rc repeat flag,
 *           dd delivery days, dl delay days, r review score, rev items revenue
 *   items   columns, one entry per item sold:  o order index, c category, p price
 * A filter is { m0, m1, state, cat } (month index range, state index or -1, category index or -1).
 */
(function (root) {
  'use strict';

  function prepare(data) {
    const o = data.orders;
    const it = data.items;
    return {
      data,
      N: o.m.length,
      K: it.o.length,
      M: data.months.length,
      C: data.categories.length,
      S: data.states.length,
      om: Int16Array.from(o.m),
      os: Int16Array.from(o.s),
      ou: Int32Array.from(o.u),
      orc: Uint8Array.from(o.rc),
      odd: Int16Array.from(o.dd),
      odl: Int16Array.from(o.dl),
      orv: Uint8Array.from(o.r),
      orev: Float64Array.from(o.rev),
      io: Int32Array.from(it.o),
      ic: Int16Array.from(it.c),
      ip: Float64Array.from(it.p),
      nCustomers: data.meta.customers,
      NO_DD: data.meta.sentinels.delivery_days,
      NO_DL: data.meta.sentinels.delay_days,
    };
  }

  /**
   * Which orders match the filter? `ignore` lets a chart skip its own dimension
   * (e.g. the category chart ignores the category filter so the other bars stay visible).
   * Returns { sel: Uint8Array(N), rev: Float64Array(N) }; with a category filter, `rev` only
   * counts the items of that category.
   */
  function select(ctx, f, ignore) {
    ignore = ignore || {};
    const { N, K, om, os, io, ic, ip, orev } = ctx;
    const useCat = f.cat >= 0 && !ignore.cat;
    const useMonth = !ignore.month;
    const useState = f.state >= 0 && !ignore.state;
    let rev = orev;
    let hasCat = null;
    if (useCat) {
      rev = new Float64Array(N);
      hasCat = new Uint8Array(N);
      for (let k = 0; k < K; k++) {
        if (ic[k] === f.cat) {
          rev[io[k]] += ip[k];
          hasCat[io[k]] = 1;
        }
      }
    }
    const sel = new Uint8Array(N);
    for (let i = 0; i < N; i++) {
      if (useMonth && (om[i] < f.m0 || om[i] > f.m1)) continue;
      if (useState && os[i] !== f.state) continue;
      if (useCat && !hasCat[i]) continue;
      sel[i] = 1;
    }
    return { sel, rev };
  }

  /** Headline KPIs for a selection. */
  function totals(ctx, s) {
    const { N, odd, odl, orv, orc, ou, nCustomers, NO_DD, NO_DL } = ctx;
    const { sel, rev } = s;
    const seen = new Uint8Array(nCustomers);
    let revenue = 0, orders = 0, ddSum = 0, ddN = 0, lateN = 0, dlN = 0;
    let rvSum = 0, rvN = 0, customers = 0, repeat = 0;
    for (let i = 0; i < N; i++) {
      if (!sel[i]) continue;
      orders++;
      revenue += rev[i];
      if (odd[i] !== NO_DD) { ddSum += odd[i]; ddN++; }
      if (odl[i] !== NO_DL) { dlN++; if (odl[i] > 0) lateN++; }
      if (orv[i] > 0) { rvSum += orv[i]; rvN++; }
      const u = ou[i];
      if (!seen[u]) { seen[u] = 1; customers++; if (orc[i]) repeat++; }
    }
    return {
      revenue,
      orders,
      aov: orders ? revenue / orders : null,
      customers,
      repeatRate: customers ? repeat / customers : null,
      avgDelivery: ddN ? ddSum / ddN : null,
      lateRate: dlN ? lateN / dlN : null,
      avgReview: rvN ? rvSum / rvN : null,
    };
  }

  /** One entry per month of the data (null metrics when the month has no sale). */
  function monthly(ctx, s) {
    const { N, M, om, ou, odd, odl, orv, NO_DD, NO_DL } = ctx;
    const { sel, rev } = s;
    const revenue = new Float64Array(M), orders = new Int32Array(M);
    const ddSum = new Float64Array(M), ddN = new Int32Array(M);
    const lateN = new Int32Array(M), dlN = new Int32Array(M);
    const rvSum = new Float64Array(M), rvN = new Int32Array(M);
    const custSeen = new Set();
    const customers = new Int32Array(M);
    for (let i = 0; i < N; i++) {
      if (!sel[i]) continue;
      const m = om[i];
      orders[m]++;
      revenue[m] += rev[i];
      if (odd[i] !== NO_DD) { ddSum[m] += odd[i]; ddN[m]++; }
      if (odl[i] !== NO_DL) { dlN[m]++; if (odl[i] > 0) lateN[m]++; }
      if (orv[i] > 0) { rvSum[m] += orv[i]; rvN[m]++; }
      const key = ou[i] * M + m;
      if (!custSeen.has(key)) { custSeen.add(key); customers[m]++; }
    }
    const out = [];
    for (let m = 0; m < M; m++) {
      const n = orders[m];
      out.push({
        month: ctx.data.months[m],
        orders: n,
        revenue: n ? revenue[m] : null,
        aov: n ? revenue[m] / n : null,
        customers: n ? customers[m] : null,
        avgDelivery: ddN[m] ? ddSum[m] / ddN[m] : null,
        lateRate: dlN[m] ? lateN[m] / dlN[m] : null,
        avgReview: rvN[m] ? rvSum[m] / rvN[m] : null,
      });
    }
    return out;
  }

  /** Revenue / distinct orders / items per category (items are sorted by order index). */
  function byCategory(ctx, s) {
    const { K, C, io, ic, ip } = ctx;
    const revenue = new Float64Array(C), orders = new Int32Array(C), items = new Int32Array(C);
    const last = new Int32Array(C).fill(-1);
    for (let k = 0; k < K; k++) {
      const o = io[k];
      if (!s.sel[o]) continue;
      const c = ic[k];
      revenue[c] += ip[k];
      items[c]++;
      if (last[c] !== o) { last[c] = o; orders[c]++; }
    }
    const rows = [];
    for (let c = 0; c < C; c++) {
      if (orders[c]) rows.push({ index: c, name: ctx.data.categories[c], revenue: revenue[c], orders: orders[c], items: items[c] });
    }
    return rows.sort((a, b) => b.revenue - a.revenue);
  }

  /** KPIs per customer state. */
  function byState(ctx, s) {
    const { N, S, os, odd, odl, orv, NO_DD, NO_DL } = ctx;
    const { sel, rev } = s;
    const acc = Array.from({ length: S }, () => ({ revenue: 0, orders: 0, ddSum: 0, ddN: 0, lateN: 0, dlN: 0, rvSum: 0, rvN: 0 }));
    for (let i = 0; i < N; i++) {
      if (!sel[i]) continue;
      const a = acc[os[i]];
      a.orders++;
      a.revenue += rev[i];
      if (odd[i] !== NO_DD) { a.ddSum += odd[i]; a.ddN++; }
      if (odl[i] !== NO_DL) { a.dlN++; if (odl[i] > 0) a.lateN++; }
      if (orv[i] > 0) { a.rvSum += orv[i]; a.rvN++; }
    }
    const rows = [];
    acc.forEach((a, index) => {
      if (!a.orders) return;
      const st = ctx.data.states[index];
      rows.push({
        index, code: st.code, name: st.name,
        revenue: a.revenue, orders: a.orders,
        avgDelivery: a.ddN ? a.ddSum / a.ddN : null,
        lateRate: a.dlN ? a.lateN / a.dlN : null,
        avgReview: a.rvN ? a.rvSum / a.rvN : null,
      });
    });
    return rows.sort((a, b) => b.revenue - a.revenue);
  }

  const DELAY_BUCKETS = [
    { key: 'early', label: 'En avance' },
    { key: 'on_time', label: 'Jour prévu' },
    { key: 'late_1_3', label: 'Retard 1 à 3 j' },
    { key: 'late_4_7', label: 'Retard 4 à 7 j' },
    { key: 'late_8_plus', label: 'Retard 8 j et +' },
  ];

  function bucketOf(delay) {
    if (delay < 0) return 0;
    if (delay === 0) return 1;
    if (delay <= 3) return 2;
    if (delay <= 7) return 3;
    return 4;
  }

  /** Average rating by delivery-delay bucket (orders delivered AND reviewed). */
  function delayBuckets(ctx, s) {
    const { N, odl, orv, NO_DL } = ctx;
    const acc = DELAY_BUCKETS.map(() => ({ orders: 0, rvSum: 0, low: 0 }));
    for (let i = 0; i < N; i++) {
      if (!s.sel[i] || odl[i] === NO_DL || orv[i] === 0) continue;
      const a = acc[bucketOf(odl[i])];
      a.orders++;
      a.rvSum += orv[i];
      if (orv[i] <= 2) a.low++;
    }
    return DELAY_BUCKETS.map((b, i) => ({
      key: b.key,
      label: b.label,
      orders: acc[i].orders,
      avgReview: acc[i].orders ? acc[i].rvSum / acc[i].orders : null,
      lowShare: acc[i].orders ? acc[i].low / acc[i].orders : null,
    }));
  }

  /** Period presets -> [firstMonthIndex, lastMonthIndex]. */
  function presetRange(name, data) {
    const months = data.months;
    const idx = (ym) => months.indexOf(ym);
    const [d0, d1] = data.meta.default_range.map(idx);
    const last = months.length - 1;
    const yearRange = (y) => {
      const first = months.findIndex((m) => m.startsWith(y));
      let end = -1;
      months.forEach((m, i) => { if (m.startsWith(y)) end = i; });
      return [first, Math.min(end, d1)];
    };
    switch (name) {
      case 'all': return [0, last];
      case 'y2017': return [Math.max(yearRange('2017')[0], d0), yearRange('2017')[1]];
      case 'y2018': return yearRange('2018');
      case 'last12': return [Math.max(d1 - 11, 0), d1];
      default: return [d0, d1]; // 'complete'
    }
  }

  // ---- formatting (French locale) -------------------------------------------------------
  const nf = (opts) => new Intl.NumberFormat('fr-FR', opts);
  const fmt = {
    int: (v) => (v == null ? '—' : nf({ maximumFractionDigits: 0 }).format(v)),
    compact: (v) => (v == null ? '—' : nf({ notation: 'compact', maximumFractionDigits: 1 }).format(v)),
    money: (v) => (v == null ? '—' : nf({ maximumFractionDigits: 0 }).format(v) + ' R$'),
    moneyCompact: (v) => (v == null ? '—' : nf({ notation: 'compact', maximumFractionDigits: 1 }).format(v) + ' R$'),
    pct: (v, d = 1) => (v == null ? '—' : nf({ style: 'percent', minimumFractionDigits: d, maximumFractionDigits: d }).format(v)),
    signedPct: (v, d = 0) => (v == null ? '—' : (v > 0 ? '+' : '') + nf({ style: 'percent', minimumFractionDigits: d, maximumFractionDigits: d }).format(v)),
    days: (v) => (v == null ? '—' : nf({ minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v) + ' j'),
    score: (v) => (v == null ? '—' : nf({ minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)),
    monthShort: (ym) => new Intl.DateTimeFormat('fr-FR', { month: 'short', year: '2-digit' }).format(new Date(+ym.slice(0, 4), +ym.slice(5, 7) - 1, 1)),
    monthLong: (ym) => new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' }).format(new Date(+ym.slice(0, 4), +ym.slice(5, 7) - 1, 1)),
    category: (c) => (c === 'unknown' ? 'Non renseignée' : c.replace(/_/g, ' ').replace(/^./, (m) => m.toUpperCase())),
  };

  const api = { prepare, select, totals, monthly, byCategory, byState, delayBuckets, DELAY_BUCKETS, presetRange, fmt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OlistMetrics = api;
})(typeof window !== 'undefined' ? window : globalThis);
