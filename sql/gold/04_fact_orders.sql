-- GOLD | fact_orders (grain: one row per order)
--
-- is_valid_sale  : the order counts as a sale = not canceled / unavailable AND has >= 1 item.
--                  Every revenue KPI is computed on valid sales only.
-- is_late        : delivered after the estimated date (NULL when not delivered).
-- customer_order_number : 1 = the customer's first valid order, 2 = second, ...
CREATE OR REPLACE TABLE gold.fact_orders AS
WITH items AS (
    SELECT
        order_id,
        count(*)           AS items_count,
        sum(price)         AS items_revenue,
        sum(freight_value) AS freight_total
    FROM silver.order_items
    GROUP BY order_id
),
pay AS (
    SELECT
        order_id,
        sum(payment_value)                    AS payment_total,
        max(installments)                     AS installments,
        arg_max(payment_type, payment_value)  AS main_payment_type
    FROM silver.payments
    GROUP BY order_id
),
base AS (
    SELECT
        o.order_id,
        c.customer_unique_id,
        CAST(strftime(o.purchased_at, '%Y%m%d') AS INTEGER)  AS purchase_date_key,
        o.purchased_at,
        o.status,
        c.state                                              AS customer_state,
        COALESCE(i.items_count, 0)                           AS items_count,
        COALESCE(i.items_revenue, 0)                         AS items_revenue,
        COALESCE(i.freight_total, 0)                         AS freight_total,
        p.payment_total,
        p.installments,
        p.main_payment_type,
        o.delivery_days,
        o.delay_days,
        CASE WHEN o.delay_days IS NULL THEN NULL ELSE o.delay_days > 0 END AS is_late,
        r.score                                              AS review_score,
        o.has_date_anomaly,
        (o.status NOT IN ('canceled', 'unavailable') AND COALESCE(i.items_count, 0) > 0) AS is_valid_sale
    FROM silver.orders o
    JOIN silver.customers c      ON c.customer_id = o.customer_id
    LEFT JOIN items i            ON i.order_id = o.order_id
    LEFT JOIN pay p              ON p.order_id = o.order_id
    LEFT JOIN silver.reviews r   ON r.order_id = o.order_id
)
SELECT
    *,
    CASE WHEN is_valid_sale
         THEN row_number() OVER (PARTITION BY customer_unique_id, is_valid_sale
                                 ORDER BY purchased_at, order_id)
    END AS customer_order_number
FROM base;
