-- SILVER | customers
-- Trim / normalise text, one row per customer_id (a customer_id is created for every order;
-- customer_unique_id identifies the real person).
CREATE OR REPLACE TABLE silver.customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix      AS zip_code_prefix,
    lower(trim(customer_city))    AS city,
    upper(trim(customer_state))   AS state
FROM bronze.customers
WHERE customer_id IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY customer_unique_id) = 1;
