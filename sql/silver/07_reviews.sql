-- SILVER | reviews
-- The source has duplicated review_id values and some orders with several reviews.
-- Rule: keep one review per order, the most recently answered one.
-- Scores outside 1..5 are rejected.
CREATE OR REPLACE TABLE silver.reviews AS
WITH typed AS (
    SELECT
        review_id,
        order_id,
        TRY_CAST(review_score AS INTEGER)              AS score,
        review_comment_title                           AS comment_title,
        review_comment_message                         AS comment_message,
        TRY_CAST(review_creation_date AS TIMESTAMP)    AS created_at,
        TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS answered_at
    FROM bronze.reviews
    WHERE order_id IS NOT NULL
)
SELECT *
FROM typed
WHERE score BETWEEN 1 AND 5
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY answered_at DESC NULLS LAST, review_id) = 1;
