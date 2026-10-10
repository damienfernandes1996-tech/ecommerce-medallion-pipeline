-- GOLD | kpi_overview: the headline numbers (single row)
CREATE OR REPLACE TABLE gold.kpi_overview AS
WITH sales AS (
    SELECT
        sum(items_revenue)                     AS total_revenue,
        sum(freight_total)                     AS total_freight,
        count(*)                               AS orders,
        sum(items_revenue) / count(*)          AS avg_order_value,
        avg(delivery_days)                     AS avg_delivery_days,
        avg(CAST(is_late AS INTEGER))          AS late_rate,
        avg(review_score)                      AS avg_review_score,
        min(purchased_at)                      AS period_start,
        max(purchased_at)                      AS period_end
    FROM gold.fact_orders
    WHERE is_valid_sale
),
customers AS (
    SELECT
        count(*)                                  AS customers,
        count(*) FILTER (WHERE is_repeat_customer) AS repeat_customers
    FROM gold.dim_customers
    WHERE orders_count > 0
)
SELECT
    s.*,
    c.customers,
    c.repeat_customers,
    c.repeat_customers * 1.0 / c.customers AS repeat_rate
FROM sales s
CROSS JOIN customers c;
