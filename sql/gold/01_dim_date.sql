-- GOLD | dim_date: one row per calendar day covering the whole order history
CREATE OR REPLACE TABLE gold.dim_date AS
WITH bounds AS (
    SELECT
        CAST(min(purchased_at) AS DATE) AS first_day,
        CAST(max(purchased_at) AS DATE) AS last_day
    FROM silver.orders
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE)                        AS date,
    year(d)                                AS year,
    quarter(d)                             AS quarter,
    month(d)                               AS month,
    strftime(d, '%Y-%m')                   AS year_month,
    monthname(d)                           AS month_name,
    isodow(d)                              AS iso_day_of_week,
    dayname(d)                             AS day_name,
    isodow(d) IN (6, 7)                    AS is_weekend
FROM bounds,
     generate_series(first_day, last_day, INTERVAL 1 DAY) AS t(d);
