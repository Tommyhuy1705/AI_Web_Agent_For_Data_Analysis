-- ============================================================
-- OMNI-REVENUE AGENT - Zero Data Lake Schema
-- Supabase (PostgreSQL) DDL
-- ============================================================

-- ============================================================
-- SCHEMA 1: raw_staging
-- Chứa dữ liệu thô đã crawl về (JSONB)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS raw_staging;

CREATE TABLE IF NOT EXISTS raw_staging.raw_sales (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(100) DEFAULT 'mock_crawler',
    data            JSONB NOT NULL,
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE
);

-- Index cho truy vấn JSONB hiệu quả
CREATE INDEX IF NOT EXISTS idx_raw_sales_data_gin
    ON raw_staging.raw_sales USING GIN (data);

CREATE INDEX IF NOT EXISTS idx_raw_sales_crawled_at
    ON raw_staging.raw_sales (crawled_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_sales_processed
    ON raw_staging.raw_sales (processed)
    WHERE processed = FALSE;

-- ============================================================
-- SCHEMA 2: analytics_mart
-- Chứa dữ liệu sạch do dbt transform sang
-- Bảng vật lý: fact_sales, dim_products, dim_customers
-- ============================================================
CREATE SCHEMA IF NOT EXISTS analytics_mart;

-- Dimension: Products
CREATE TABLE IF NOT EXISTS analytics_mart.dim_products (
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
    ON analytics_mart.dim_products (category);

-- Dimension: Customers
CREATE TABLE IF NOT EXISTS analytics_mart.dim_customers (
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
    ON analytics_mart.dim_customers (segment);

CREATE INDEX IF NOT EXISTS idx_dim_customers_region
    ON analytics_mart.dim_customers (region);

-- Fact: Sales
CREATE TABLE IF NOT EXISTS analytics_mart.fact_sales (
    sale_id         BIGSERIAL PRIMARY KEY,
    order_date      DATE NOT NULL,
    product_id      INTEGER REFERENCES analytics_mart.dim_products(product_id),
    customer_id     INTEGER REFERENCES analytics_mart.dim_customers(customer_id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12, 2) NOT NULL,
    total_amount    NUMERIC(14, 2) NOT NULL,
    discount        NUMERIC(5, 2) DEFAULT 0,
    channel         VARCHAR(50) DEFAULT 'online',
    payment_method  VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_order_date
    ON analytics_mart.fact_sales (order_date DESC);

CREATE INDEX IF NOT EXISTS idx_fact_sales_product_id
    ON analytics_mart.fact_sales (product_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_id
    ON analytics_mart.fact_sales (customer_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_channel
    ON analytics_mart.fact_sales (channel);

-- ============================================================
-- Market Intelligence: Raw data from TinyFish crawlers
-- Chứa dữ liệu cào từ Shopee, Tiki, Alibaba, etc.
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_staging.raw_market_intel (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,       -- 'shopee', 'tiki', 'alibaba', etc.
    crawl_type      VARCHAR(50) NOT NULL,       -- 'competitor_price', 'review', 'material_cost'
    keyword         VARCHAR(255),               -- Từ khóa tìm kiếm
    raw_data        JSONB NOT NULL,             -- Nguyên cục JSON do TinyFish cào về
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_source
    ON raw_staging.raw_market_intel (source);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_crawl_type
    ON raw_staging.raw_market_intel (crawl_type);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_data_gin
    ON raw_staging.raw_market_intel USING GIN (raw_data);

CREATE INDEX IF NOT EXISTS idx_raw_market_intel_crawled_at
    ON raw_staging.raw_market_intel (crawled_at DESC);

-- ============================================================
-- SECURITY: Read-only role for AI SQL proxy
-- Run manually with secure password in Supabase SQL editor.
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_ai') THEN
        CREATE ROLE readonly_ai LOGIN PASSWORD 'change_me_strong_password';
    END IF;
END $$;

GRANT USAGE ON SCHEMA analytics_mart TO readonly_ai;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics_mart TO readonly_ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics_mart
GRANT SELECT ON TABLES TO readonly_ai;

-- ============================================================
-- SCHEMA 3: system_metrics
-- Bảng hourly_snapshot để lưu kết quả tính toán mỗi giờ
-- Dùng cho tính năng Proactive Alarm
-- ============================================================
CREATE SCHEMA IF NOT EXISTS system_metrics;

CREATE TABLE IF NOT EXISTS system_metrics.hourly_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     VARCHAR(100) NOT NULL,
    value           NUMERIC(18, 4) NOT NULL,
    previous_value  NUMERIC(18, 4),
    change_pct      NUMERIC(8, 4),
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(metric_name)
);

CREATE INDEX IF NOT EXISTS idx_hourly_snapshot_metric
    ON system_metrics.hourly_snapshot (metric_name);

CREATE INDEX IF NOT EXISTS idx_hourly_snapshot_updated
    ON system_metrics.hourly_snapshot (last_updated DESC);

-- ============================================================
-- HELPER VIEWS cho analytics_mart
-- ============================================================

-- View: Doanh thu theo ngày
CREATE OR REPLACE VIEW analytics_mart.v_daily_revenue AS
SELECT
    order_date,
    COUNT(*) AS total_orders,
    SUM(quantity) AS total_quantity,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM analytics_mart.fact_sales
GROUP BY order_date
ORDER BY order_date DESC;

-- View: Doanh thu theo sản phẩm
CREATE OR REPLACE VIEW analytics_mart.v_product_performance AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(f.sale_id) AS total_orders,
    SUM(f.quantity) AS total_quantity,
    SUM(f.total_amount) AS total_revenue
FROM analytics_mart.fact_sales f
JOIN analytics_mart.dim_products p ON f.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC;

-- View: Doanh thu theo khách hàng segment
CREATE OR REPLACE VIEW analytics_mart.v_customer_segment_revenue AS
SELECT
    c.segment,
    c.region,
    COUNT(DISTINCT c.customer_id) AS total_customers,
    COUNT(f.sale_id) AS total_orders,
    SUM(f.total_amount) AS total_revenue
FROM analytics_mart.fact_sales f
JOIN analytics_mart.dim_customers c ON f.customer_id = c.customer_id
GROUP BY c.segment, c.region
ORDER BY total_revenue DESC;

-- View: Doanh thu theo tháng (cho Predictive Analytics)
CREATE OR REPLACE VIEW analytics_mart.v_monthly_revenue AS
SELECT
    DATE_TRUNC('month', order_date)::DATE AS month,
    COUNT(*) AS total_orders,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM analytics_mart.fact_sales
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month DESC;
