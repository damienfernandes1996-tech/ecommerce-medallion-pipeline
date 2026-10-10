-- GOLD | kpi_monthly: the main trend table (valid sales only)
CREATE OR REPLACE TABLE gold.kpi_monthly AS
WITH monthly AS (
    SELECT
        strftime(purchased_at, '%Y-%m')                         AS year_month,
        count(*)                                                AS orders,
        sum(items_revenue)                                      AS revenue,
        sum(freight_total)                                      AS freight,
        count(DISTINCT customer_unique_id)                      AS customers,
        count(*) FILTER (WHERE customer_order_number = 1)       AS new_customers,
        avg(delivery_days)                                      AS avg_delivery_days,
        avg(CAST(is_late AS INTEGER))                           AS late_rate,
        avg(review_score)                                       AS avg_review_score
    FROM gold.fact_orders
    WHERE is_valid_sale
    GROUP BY 1
)
SELECT
    year_month,
    orders,
    revenue,
    freight,
    revenue / orders                                            AS avg_order_value,
    customers,
    new_customers,
    avg_delivery_days,
    late_rate,
    avg_review_score,
    -- growth vs the previous calendar month (NULL when that month has no sales at all)
    CASE
        WHEN date_diff('month',
                       CAST(lag(year_month) OVER (ORDER BY year_month) || '-01' AS DATE),
                       CAST(year_month || '-01' AS DATE)) = 1
        THEN revenue / NULLIF(lag(revenue) OVER (ORDER BY year_month), 0) - 1
    END                                                         AS revenue_mom_growth
FROM monthly
ORDER BY year_month;
