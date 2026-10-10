-- SILVER | payments (an order can be paid with several payment lines)
CREATE OR REPLACE TABLE silver.payments AS
SELECT
    order_id,
    TRY_CAST(payment_sequential AS INTEGER)    AS payment_sequential,
    lower(trim(payment_type))                  AS payment_type,
    TRY_CAST(payment_installments AS INTEGER)  AS installments,
    TRY_CAST(payment_value AS DOUBLE)          AS payment_value
FROM bronze.payments
WHERE order_id IS NOT NULL
  AND TRY_CAST(payment_value AS DOUBLE) IS NOT NULL;
