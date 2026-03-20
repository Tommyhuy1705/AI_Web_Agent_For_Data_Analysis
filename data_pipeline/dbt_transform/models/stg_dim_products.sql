-- ============================================================
-- dbt Model: stg_dim_products
-- Bóc tách JSONB từ raw_staging.raw_sales sang dim_products
-- ============================================================

{{
    config(
        materialized='table',
        schema='analytics_mart',
        alias='dim_products'
    )
}}

WITH raw_products AS (
    SELECT DISTINCT
        data->'product'->>'name' AS product_name,
        data->'product'->>'category' AS category,
        data->'product'->>'sub_category' AS sub_category,
        data->'product'->>'brand' AS brand,
        (data->'product'->>'unit_price')::NUMERIC(12, 2) AS unit_price
    FROM raw_staging.raw_sales
    WHERE data->'product'->>'name' IS NOT NULL
)

SELECT
    ROW_NUMBER() OVER (ORDER BY product_name) AS product_id,
    product_name,
    category,
    sub_category,
    brand,
    unit_price,
    NOW() AS created_at,
    NOW() AS updated_at
FROM raw_products
