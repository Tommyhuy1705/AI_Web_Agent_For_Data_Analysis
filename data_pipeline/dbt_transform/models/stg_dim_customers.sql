-- ============================================================
-- dbt Model: stg_dim_customers
-- Bóc tách JSONB từ raw_staging.raw_sales sang dim_customers
-- ============================================================

{{
    config(
        materialized='table',
        schema='analytics_mart',
        alias='dim_customers'
    )
}}

WITH raw_customers AS (
    SELECT DISTINCT
        data->'customer'->>'name' AS customer_name,
        data->'customer'->>'email' AS email,
        data->'customer'->>'segment' AS segment,
        data->'customer'->>'region' AS region,
        data->'customer'->>'city' AS city
    FROM raw_staging.raw_sales
    WHERE data->'customer'->>'name' IS NOT NULL
)

SELECT
    ROW_NUMBER() OVER (ORDER BY customer_name) AS customer_id,
    customer_name,
    email,
    segment,
    region,
    city,
    'Vietnam' AS country,
    NOW() AS created_at,
    NOW() AS updated_at
FROM raw_customers
