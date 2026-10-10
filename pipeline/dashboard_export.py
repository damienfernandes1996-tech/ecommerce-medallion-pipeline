"""Export the Gold layer to dashboard/data.js (the only input of the interactive dashboard).

Compact, column-oriented JSON:
  * `orders`: one entry per valid sale (column arrays, same index = same order)
  * `items` : one entry per item sold, `o` = index of its order in `orders`
Every number shown by the dashboard is computed in the browser from these two tables, so a
filter (period / state / category) can recompute exact KPIs, including distinct counts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from .config import Paths

# Brazilian state codes (UF) -> names
STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}

NO_DELIVERY = -1      # sentinel: delivery_days unknown (order not delivered)
NO_DELAY = -999       # sentinel: delay_days unknown (real values go down to about -150)
NO_REVIEW = 0         # sentinel: no review


def _month_range(first: str, last: str) -> list[str]:
    """Contiguous list of 'YYYY-MM' between two months (inclusive)."""
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_payload(con: duckdb.DuckDBPyConnection) -> dict:
    order_rows = con.execute(
        """
        SELECT
            o.order_id,
            strftime(o.purchased_at, '%Y-%m')                    AS year_month,
            o.customer_state,
            o.customer_unique_id,
            COALESCE(c.is_repeat_customer, FALSE)                AS is_repeat,
            o.delivery_days,
            o.delay_days,
            o.review_score,
            o.items_revenue
        FROM gold.fact_orders o
        JOIN gold.dim_customers c USING (customer_unique_id)
        WHERE o.is_valid_sale
        ORDER BY o.order_id
        """
    ).fetchall()

    item_rows = con.execute(
        """
        SELECT i.order_id, p.category, i.price
        FROM gold.fact_order_items i
        JOIN gold.dim_products p USING (product_id)
        WHERE i.is_valid_sale
        ORDER BY i.order_id, i.order_item_id
        """
    ).fetchall()

    categories = [r[0] for r in con.execute(
        "SELECT category FROM gold.kpi_category ORDER BY revenue DESC").fetchall()]
    states = [r[0] for r in con.execute(
        "SELECT state FROM gold.kpi_state ORDER BY revenue DESC").fetchall()]
    monthly = con.execute(
        "SELECT year_month, orders FROM gold.kpi_monthly ORDER BY year_month").fetchall()

    months = _month_range(monthly[0][0], monthly[-1][0])
    month_idx = {m: i for i, m in enumerate(months)}
    state_idx = {s: i for i, s in enumerate(states)}
    cat_idx = {c: i for i, c in enumerate(categories)}

    customer_idx: dict[str, int] = {}
    order_idx: dict[str, int] = {}
    cols = {k: [] for k in ("m", "s", "u", "rc", "dd", "dl", "r", "rev")}
    for i, (oid, ym, state, cust, rep, dd, dl, rv, rev) in enumerate(order_rows):
        order_idx[oid] = i
        cols["m"].append(month_idx[ym])
        cols["s"].append(state_idx[state])
        cols["u"].append(customer_idx.setdefault(cust, len(customer_idx)))
        cols["rc"].append(1 if rep else 0)
        cols["dd"].append(NO_DELIVERY if dd is None else int(dd))
        cols["dl"].append(NO_DELAY if dl is None else int(dl))
        cols["r"].append(NO_REVIEW if rv is None else int(rv))
        cols["rev"].append(round(float(rev), 2))

    items = {"o": [], "c": [], "p": []}
    for oid, cat, price in item_rows:
        items["o"].append(order_idx[oid])
        items["c"].append(cat_idx[cat])
        items["p"].append(round(float(price), 2))

    # Default period = "complete months": drop the ramp-up / cut-off months whose volume is
    # below 5% of the peak month (Oct-Dec 2016 and Sep-Oct 2018 in the Olist data).
    peak = max(n for _, n in monthly)
    complete = [m for m, n in monthly if n >= 0.05 * peak]
    default_range = [complete[0], complete[-1]]

    ov = con.execute(
        "SELECT total_revenue, orders, customers, period_start, period_end FROM gold.kpi_overview"
    ).fetchone()

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "source": "Olist Brazilian E-Commerce Public Dataset (CC BY-NC-SA 4.0)",
            "currency": "BRL",
            "orders": len(order_rows),
            "items": len(item_rows),
            "customers": len(customer_idx),
            "total_revenue": round(float(ov[0]), 2),
            "period_start": str(ov[3])[:10],
            "period_end": str(ov[4])[:10],
            "default_range": default_range,
            "sentinels": {"delivery_days": NO_DELIVERY, "delay_days": NO_DELAY, "review": NO_REVIEW},
        },
        "months": months,
        "states": [{"code": s, "name": STATE_NAMES.get(s, s)} for s in states],
        "categories": categories,
        "orders": cols,
        "items": items,
    }


def run(paths: Paths) -> dict:
    con = duckdb.connect(str(paths.warehouse), read_only=True)
    try:
        payload = build_payload(con)
    finally:
        con.close()
    paths.dashboard.mkdir(parents=True, exist_ok=True)
    target = paths.dashboard / "data.js"
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    target.write_text(f"window.OLIST_DATA = {body};\n", encoding="utf-8")
    size_mb = target.stat().st_size / 1e6
    print(f"    {target.name}: {payload['meta']['orders']:,} orders, "
          f"{payload['meta']['items']:,} items, {size_mb:.1f} MB")
    return {**payload["meta"], "file_mb": round(size_mb, 2)}
