-- GOLD | dim_products
CREATE OR REPLACE TABLE gold.dim_products AS
SELECT
    product_id,
    category,
    photos_qty,
    weight_g,
    length_cm * height_cm * width_cm AS volume_cm3
FROM silver.products;
