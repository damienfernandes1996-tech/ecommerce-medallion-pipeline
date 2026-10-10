-- GOLD | kpi_category: performance by product category (valid sales only)
-- "orders" = distinct orders that contain at least one item of the category.
CREATE OR REPLACE TABLE gold.kpi_category AS
WITH order_category AS (
    SELECT
        p.category,
        i.order_id,
        sum(i.price) AS revenue,
        count(*)     AS items
    FROM gold.fact_order_items i
    JOIN gold.dim_products p ON p.product_id = i.product_id
    WHERE i.is_valid_sale
    GROUP BY p.category, i.order_id
)
SELECT
    oc.category,
    count(*)                                              AS orders,
    sum(oc.revenue)                                       AS revenue,
    sum(oc.items)                                         AS items,
    sum(oc.revenue) / sum(oc.items)                       AS avg_item_price,
    avg(o.review_score)                                   AS avg_review_score,
    sum(oc.revenue) / sum(sum(oc.revenue)) OVER ()        AS revenue_share
FROM order_category oc
JOIN gold.fact_orders o ON o.order_id = oc.order_id
GROUP BY oc.category
ORDER BY revenue DESC;
