-- GOLD | dim_customers (grain: one row per real customer = customer_unique_id)
CREATE OR REPLACE TABLE gold.dim_customers AS
SELECT
    customer_unique_id,
    arg_max(customer_state, purchased_at)                       AS state,
    count(*) FILTER (WHERE is_valid_sale)                       AS orders_count,
    min(purchased_at) FILTER (WHERE is_valid_sale)              AS first_order_at,
    max(purchased_at) FILTER (WHERE is_valid_sale)              AS last_order_at,
    count(*) FILTER (WHERE is_valid_sale) > 1                   AS is_repeat_customer,
    CASE
        WHEN count(*) FILTER (WHERE is_valid_sale) = 0 THEN 'no_valid_order'
        WHEN count(*) FILTER (WHERE is_valid_sale) = 1 THEN 'one_time'
        ELSE 'repeat'
    END                                                         AS segment
FROM gold.fact_orders
GROUP BY customer_unique_id;
