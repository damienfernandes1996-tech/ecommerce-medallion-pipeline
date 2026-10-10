-- GOLD | dim_sellers
CREATE OR REPLACE TABLE gold.dim_sellers AS
SELECT seller_id, city, state
FROM silver.sellers;
