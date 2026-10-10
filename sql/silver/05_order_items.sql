-- SILVER | order_items (grain: one row per item of an order)
CREATE OR REPLACE TABLE silver.order_items AS
SELECT
    order_id,
    TRY_CAST(order_item_id AS INTEGER)       AS order_item_id,
    product_id,
    seller_id,
    TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_at,
    TRY_CAST(price AS DOUBLE)                AS price,
    TRY_CAST(freight_value AS DOUBLE)        AS freight_value
FROM bronze.order_items
WHERE order_id IS NOT NULL
  AND product_id IS NOT NULL
  AND TRY_CAST(price AS DOUBLE) IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY order_id, order_item_id ORDER BY product_id) = 1;
