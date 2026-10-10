-- GOLD | kpi_delivery_review: how the delivery delay affects the customer rating
-- delay_days < 0  : delivered before the estimated date
-- delay_days = 0  : delivered on the estimated day
-- delay_days > 0  : late
CREATE OR REPLACE TABLE gold.kpi_delivery_review AS
WITH bucketed AS (
    SELECT
        CASE
            WHEN delay_days < 0  THEN 'early'
            WHEN delay_days = 0  THEN 'on_time'
            WHEN delay_days <= 3 THEN 'late_1_3'
            WHEN delay_days <= 7 THEN 'late_4_7'
            ELSE 'late_8_plus'
        END AS delay_bucket,
        review_score
    FROM gold.fact_orders
    WHERE is_valid_sale AND delay_days IS NOT NULL AND review_score IS NOT NULL
)
SELECT
    delay_bucket,
    CASE delay_bucket
        WHEN 'early' THEN 1 WHEN 'on_time' THEN 2 WHEN 'late_1_3' THEN 3
        WHEN 'late_4_7' THEN 4 ELSE 5
    END                                                   AS bucket_order,
    count(*)                                              AS orders,
    avg(review_score)                                     AS avg_review_score,
    avg(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END) AS low_score_share
FROM bucketed
GROUP BY delay_bucket
ORDER BY bucket_order;
