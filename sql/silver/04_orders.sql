-- SILVER | orders
-- * timestamps are cast (invalid values become NULL instead of failing the load)
-- * delivery_days / delay_days are only computed for delivered orders with a coherent
--   timeline (delivered_at >= purchased_at)
-- * delay_days > 0 means the order arrived after the estimated date
CREATE OR REPLACE TABLE silver.orders AS
WITH typed AS (
    SELECT
        order_id,
        customer_id,
        lower(trim(order_status))                              AS status,
        TRY_CAST(order_purchase_timestamp AS TIMESTAMP)        AS purchased_at,
        TRY_CAST(order_approved_at AS TIMESTAMP)               AS approved_at,
        TRY_CAST(order_delivered_carrier_date AS TIMESTAMP)    AS shipped_at,
        TRY_CAST(order_delivered_customer_date AS TIMESTAMP)   AS delivered_at,
        TRY_CAST(order_estimated_delivery_date AS TIMESTAMP)   AS estimated_delivery_at
    FROM bronze.orders
    WHERE order_id IS NOT NULL
    QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY order_purchase_timestamp DESC) = 1
)
SELECT
    *,
    CASE WHEN status = 'delivered' AND delivered_at >= purchased_at
         THEN date_diff('day', CAST(purchased_at AS DATE), CAST(delivered_at AS DATE))
    END                                                        AS delivery_days,
    CASE WHEN status = 'delivered' AND delivered_at >= purchased_at
         THEN date_diff('day', CAST(estimated_delivery_at AS DATE), CAST(delivered_at AS DATE))
    END                                                        AS delay_days,
    COALESCE(delivered_at < purchased_at, FALSE)               AS has_date_anomaly
FROM typed;
