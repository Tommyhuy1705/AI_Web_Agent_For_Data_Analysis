-- ============================================================
-- OMNI-REVENUE AGENT - Public Schema DDL
-- For Supabase PostgREST compatibility
-- Run this in Supabase Dashboard > SQL Editor
-- ============================================================

-- Dimension: Products
CREATE TABLE IF NOT EXISTS public.dim_products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    sub_category    VARCHAR(100),
    brand           VARCHAR(100),
    unit_price      NUMERIC(12, 2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_products_category
    ON public.dim_products (category);

-- Dimension: Customers
CREATE TABLE IF NOT EXISTS public.dim_customers (
    customer_id     SERIAL PRIMARY KEY,
    customer_name   VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    segment         VARCHAR(50),
    region          VARCHAR(100),
    city            VARCHAR(100),
    country         VARCHAR(100) DEFAULT 'Vietnam',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_customers_segment
    ON public.dim_customers (segment);
CREATE INDEX IF NOT EXISTS idx_dim_customers_region
    ON public.dim_customers (region);

-- Fact: Sales
CREATE TABLE IF NOT EXISTS public.fact_sales (
    sale_id         BIGSERIAL PRIMARY KEY,
    order_date      DATE NOT NULL,
    product_id      INTEGER REFERENCES public.dim_products(product_id),
    customer_id     INTEGER REFERENCES public.dim_customers(customer_id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12, 2) NOT NULL,
    total_amount    NUMERIC(14, 2) NOT NULL,
    discount        NUMERIC(5, 2) DEFAULT 0,
    channel         VARCHAR(50) DEFAULT 'online',
    payment_method  VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_order_date
    ON public.fact_sales (order_date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product_id
    ON public.fact_sales (product_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_id
    ON public.fact_sales (customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_channel
    ON public.fact_sales (channel);

-- System Metrics: Hourly Snapshot
CREATE TABLE IF NOT EXISTS public.hourly_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     VARCHAR(100) NOT NULL UNIQUE,
    value           NUMERIC(18, 4) NOT NULL,
    previous_value  NUMERIC(18, 4),
    change_pct      NUMERIC(8, 4),
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hourly_snapshot_metric
    ON public.hourly_snapshot (metric_name);

-- Raw Staging
CREATE TABLE IF NOT EXISTS public.raw_sales (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(100) DEFAULT 'mock_crawler',
    data            JSONB NOT NULL,
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raw_sales_data_gin
    ON public.raw_sales USING GIN (data);

-- ============================================================
-- Market Intelligence: Raw data from TinyFish crawlers
-- ============================================================
CREATE TABLE IF NOT EXISTS public.raw_market_intel (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,       -- 'shopee', 'tiki', 'alibaba', etc.
    crawl_type      VARCHAR(50) NOT NULL,       -- 'competitor_price', 'review', 'material_cost'
    keyword         VARCHAR(255),               -- Từ khóa tìm kiếm
    raw_data        JSONB NOT NULL,             -- Nguyên cục JSON do TinyFish cào về
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_source
    ON public.raw_market_intel (source);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_crawl_type
    ON public.raw_market_intel (crawl_type);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_data_gin
    ON public.raw_market_intel USING GIN (raw_data);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_crawled_at
    ON public.raw_market_intel (crawled_at DESC);

-- Competitor Prices (Materialized from raw_market_intel)
CREATE TABLE IF NOT EXISTS public.competitor_prices (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,
    product_name    VARCHAR(500) NOT NULL,
    price           NUMERIC(14, 2),
    original_price  NUMERIC(14, 2),
    discount_pct    NUMERIC(5, 2) DEFAULT 0,
    sold_count      INTEGER DEFAULT 0,
    rating          NUMERIC(3, 2),
    seller_name     VARCHAR(255),
    product_url     TEXT,
    keyword         VARCHAR(255),
    crawled_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_competitor_prices_source
    ON public.competitor_prices (source);

CREATE INDEX IF NOT EXISTS idx_competitor_prices_keyword
    ON public.competitor_prices (keyword);

CREATE INDEX IF NOT EXISTS idx_competitor_prices_crawled_at
    ON public.competitor_prices (crawled_at DESC);

-- ============================================================
-- VIEWS for analytics
-- ============================================================

-- View: Daily Revenue
CREATE OR REPLACE VIEW public.v_daily_revenue AS
SELECT
    order_date,
    COUNT(*) AS total_orders,
    SUM(quantity) AS total_quantity,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM public.fact_sales
GROUP BY order_date
ORDER BY order_date DESC;

-- View: Product Performance
CREATE OR REPLACE VIEW public.v_product_performance AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(f.sale_id) AS total_orders,
    SUM(f.quantity) AS total_quantity,
    SUM(f.total_amount) AS total_revenue
FROM public.fact_sales f
JOIN public.dim_products p ON f.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC;

-- View: Customer Segment Revenue
CREATE OR REPLACE VIEW public.v_customer_segment_revenue AS
SELECT
    c.segment,
    c.region,
    COUNT(DISTINCT c.customer_id) AS total_customers,
    COUNT(f.sale_id) AS total_orders,
    SUM(f.total_amount) AS total_revenue
FROM public.fact_sales f
JOIN public.dim_customers c ON f.customer_id = c.customer_id
GROUP BY c.segment, c.region
ORDER BY total_revenue DESC;

-- View: Monthly Revenue (for Predictive Analytics)
CREATE OR REPLACE VIEW public.v_monthly_revenue AS
SELECT
    DATE_TRUNC('month', order_date)::DATE AS month,
    COUNT(*) AS total_orders,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM public.fact_sales
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month DESC;

-- View: Competitor Price Summary
CREATE OR REPLACE VIEW public.v_competitor_price_summary AS
SELECT
    source,
    keyword,
    COUNT(*) AS total_products,
    AVG(price) AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    AVG(discount_pct) AS avg_discount,
    AVG(sold_count) AS avg_sold_count,
    MAX(crawled_at) AS last_crawled
FROM public.competitor_prices
GROUP BY source, keyword
ORDER BY last_crawled DESC;

-- View: Latest Market Intel
CREATE OR REPLACE VIEW public.v_latest_market_intel AS
SELECT
    id, source, crawl_type, keyword,
    raw_data,
    crawled_at
FROM public.raw_market_intel
WHERE crawled_at >= NOW() - INTERVAL '7 days'
ORDER BY crawled_at DESC;

-- ============================================================
-- RPC Function: exec_sql (for dynamic SQL execution)
-- ============================================================
CREATE OR REPLACE FUNCTION public.exec_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
BEGIN
    -- Only allow SELECT queries
    IF NOT (UPPER(TRIM(query)) LIKE 'SELECT%') THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;

    EXECUTE 'SELECT json_agg(row_to_json(t)) FROM (' || query || ') t'
    INTO result;

    RETURN COALESCE(result, '[]'::json);
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION public.exec_sql(text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.exec_sql(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.exec_sql(text) TO anon;

-- ============================================================
-- Enable Row Level Security (RLS) but allow all for service_role
-- ============================================================
ALTER TABLE public.dim_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dim_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fact_sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hourly_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_sales ENABLE ROW LEVEL SECURITY;

-- Allow service_role full access
CREATE POLICY "Service role full access" ON public.dim_products FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.dim_customers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.fact_sales FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.hourly_snapshot FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.raw_sales FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Allow anon read access
CREATE POLICY "Anon read access" ON public.dim_products FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read access" ON public.dim_customers FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read access" ON public.fact_sales FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read access" ON public.hourly_snapshot FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read access" ON public.raw_sales FOR SELECT TO anon USING (true);

-- Market Intel tables
ALTER TABLE public.raw_market_intel ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competitor_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON public.raw_market_intel FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON public.competitor_prices FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Anon read access" ON public.raw_market_intel FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read access" ON public.competitor_prices FOR SELECT TO anon USING (true);
