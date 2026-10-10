-- GOLD | fact_order_items (grain: one row per item sold)
CREATE OR REPLACE TABLE gold.fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    o.customer_unique_id,
    o.purchase_date_key,
    o.is_valid_sale,
    i.price,
    i.freight_value,
    i.price + i.freight_value AS item_total
FROM silver.order_items i
JOIN gold.fact_orders o ON o.order_id = i.order_id;
