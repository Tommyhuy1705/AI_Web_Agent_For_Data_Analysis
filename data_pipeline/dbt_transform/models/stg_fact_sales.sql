-- ============================================================
-- dbt Model: stg_fact_sales
-- Bóc tách JSONB từ raw_staging.raw_sales sang fact_sales
-- Join với dim_products và dim_customers để lấy FK
-- ============================================================

{{
    config(
        materialized='table',
        schema='analytics_mart',
        alias='fact_sales'
    )
}}

WITH raw_sales AS (
    SELECT
        id AS raw_id,
        data->>'order_id' AS order_id,
        (data->>'order_date')::DATE AS order_date,
        data->'product'->>'name' AS product_name,
        data->'customer'->>'name' AS customer_name,
        (data->>'quantity')::INTEGER AS quantity,
        (data->'product'->>'unit_price')::NUMERIC(12, 2) AS unit_price,
        (data->>'total_amount')::NUMERIC(14, 2) AS total_amount,
        (data->>'discount_pct')::NUMERIC(5, 2) AS discount,
        data->>'channel' AS channel,
        data->>'payment_method' AS payment_method,
        data->>'status' AS status
    FROM public.raw_sales
    WHERE data->>'status' = 'completed'
),

products AS (
    SELECT product_id, product_name
    FROM {{ ref('stg_dim_products') }}
),

customers AS (
    SELECT customer_id, customer_name
    FROM {{ ref('stg_dim_customers') }}
)

SELECT
    ROW_NUMBER() OVER (ORDER BY rs.order_date, rs.raw_id) AS sale_id,
    rs.order_id,
    rs.order_date,
    p.product_id,
    c.customer_id,
    rs.quantity,
    rs.unit_price,
    rs.total_amount,
    rs.discount,
    rs.channel,
    rs.payment_method,
    NOW() AS created_at
FROM raw_sales rs
LEFT JOIN products p ON rs.product_name = p.product_name
LEFT JOIN customers c ON rs.customer_name = c.customer_name
