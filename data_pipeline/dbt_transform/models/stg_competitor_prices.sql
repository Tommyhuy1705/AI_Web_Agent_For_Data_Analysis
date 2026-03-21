-- ============================================================
-- stg_competitor_prices
-- Transform raw_market_intel JSONB → competitor_prices table
-- Nguồn: TinyFish crawl data từ Shopee, Tiki, Alibaba
-- ============================================================

{{
    config(
        materialized='table',
        schema='analytics_mart',
        alias='competitor_prices_mart'
    )
}}

WITH raw_intel AS (
    SELECT
        id,
        source,
        crawl_type,
        keyword,
        raw_data,
        crawled_at
    FROM {{ source('public', 'raw_market_intel') }}
    WHERE crawl_type = 'competitor_price'
      AND processed = FALSE
),

-- Extract products from JSONB array
extracted_products AS (
    SELECT
        ri.id AS raw_id,
        ri.source,
        ri.keyword,
        ri.crawled_at,
        product_item.value AS product_json
    FROM raw_intel ri,
    LATERAL jsonb_array_elements(
        CASE
            WHEN ri.raw_data ? 'products' THEN ri.raw_data->'products'
            WHEN jsonb_typeof(ri.raw_data) = 'array' THEN ri.raw_data
            ELSE '[]'::jsonb
        END
    ) AS product_item(value)
)

SELECT
    ROW_NUMBER() OVER (ORDER BY ep.crawled_at DESC, ep.raw_id) AS competitor_price_id,
    ep.source,
    COALESCE(ep.product_json->>'product_name', ep.product_json->>'name', 'Unknown') AS product_name,
    CAST(NULLIF(REGEXP_REPLACE(COALESCE(ep.product_json->>'price', '0'), '[^0-9.]', '', 'g'), '') AS NUMERIC(14,2)) AS price,
    CAST(NULLIF(REGEXP_REPLACE(COALESCE(ep.product_json->>'original_price', '0'), '[^0-9.]', '', 'g'), '') AS NUMERIC(14,2)) AS original_price,
    COALESCE(CAST(NULLIF(REGEXP_REPLACE(COALESCE(ep.product_json->>'discount_percentage', ep.product_json->>'discount_pct', '0'), '[^0-9.]', '', 'g'), '') AS NUMERIC(5,2)), 0) AS discount_pct,
    COALESCE(CAST(NULLIF(REGEXP_REPLACE(COALESCE(ep.product_json->>'number_of_items_sold', ep.product_json->>'sold_count', '0'), '[^0-9]', '', 'g'), '') AS INTEGER), 0) AS sold_count,
    COALESCE(CAST(NULLIF(ep.product_json->>'rating', '') AS NUMERIC(3,2)), 0) AS rating,
    COALESCE(ep.product_json->>'seller_name', '') AS seller_name,
    COALESCE(ep.product_json->>'product_url', '') AS product_url,
    ep.keyword,
    ep.crawled_at
FROM extracted_products ep
WHERE ep.product_json->>'product_name' IS NOT NULL
   OR ep.product_json->>'name' IS NOT NULL
