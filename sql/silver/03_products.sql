-- SILVER | products
-- * fixes the misspelled source columns (name_lenght -> name_length)
-- * translates category names to English
-- * products without a category become 'unknown' instead of NULL
CREATE OR REPLACE TABLE silver.products AS
WITH translation AS (
    SELECT product_category_name AS category_pt, product_category_name_english AS category_en
    FROM bronze.category_translation
    UNION ALL
    -- two categories exist in products but are missing from the official translation file
    SELECT 'pc_gamer', 'pc_gamer'
    UNION ALL
    SELECT 'portateis_cozinha_e_preparadores_de_alimentos', 'portable_kitchen_and_food_preparers'
)
SELECT
    p.product_id,
    COALESCE(t.category_en, 'unknown')                     AS category,
    TRY_CAST(p.product_name_lenght AS INTEGER)             AS name_length,
    TRY_CAST(p.product_description_lenght AS INTEGER)      AS description_length,
    TRY_CAST(p.product_photos_qty AS INTEGER)              AS photos_qty,
    TRY_CAST(p.product_weight_g AS DOUBLE)                 AS weight_g,
    TRY_CAST(p.product_length_cm AS DOUBLE)                AS length_cm,
    TRY_CAST(p.product_height_cm AS DOUBLE)                AS height_cm,
    TRY_CAST(p.product_width_cm AS DOUBLE)                 AS width_cm
FROM bronze.products p
LEFT JOIN translation t ON t.category_pt = p.product_category_name
WHERE p.product_id IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY p.product_id ORDER BY t.category_en) = 1;
