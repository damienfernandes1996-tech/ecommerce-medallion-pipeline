-- SILVER | sellers
CREATE OR REPLACE TABLE silver.sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix      AS zip_code_prefix,
    lower(trim(seller_city))    AS city,
    upper(trim(seller_state))   AS state
FROM bronze.sellers
WHERE seller_id IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY seller_id ORDER BY seller_zip_code_prefix) = 1;
