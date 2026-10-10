-- GOLD | kpi_state: performance by customer state (valid sales only)
CREATE OR REPLACE TABLE gold.kpi_state AS
SELECT
    customer_state                                        AS state,
    count(*)                                              AS orders,
    sum(items_revenue)                                    AS revenue,
    count(DISTINCT customer_unique_id)                    AS customers,
    sum(items_revenue) / count(*)                         AS avg_order_value,
    avg(delivery_days)                                    AS avg_delivery_days,
    avg(CAST(is_late AS INTEGER))                         AS late_rate,
    avg(review_score)                                     AS avg_review_score,
    sum(items_revenue) / sum(sum(items_revenue)) OVER ()  AS revenue_share
FROM gold.fact_orders
WHERE is_valid_sale
GROUP BY customer_state
ORDER BY revenue DESC;
