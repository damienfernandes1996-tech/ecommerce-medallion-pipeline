-- GOLD | kpi_payment: split by main payment method (valid sales only)
CREATE OR REPLACE TABLE gold.kpi_payment AS
SELECT
    COALESCE(main_payment_type, 'unknown')                AS payment_type,
    count(*)                                              AS orders,
    sum(items_revenue)                                    AS revenue,
    avg(installments)                                     AS avg_installments,
    sum(items_revenue) / sum(sum(items_revenue)) OVER ()  AS revenue_share
FROM gold.fact_orders
WHERE is_valid_sale
GROUP BY 1
ORDER BY revenue DESC;
