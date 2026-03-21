"""
Setup Database - Initialize Supabase tables and seed mock data.
Uses Supabase REST API (PostgREST) since direct PostgreSQL connection
may not be available from all environments.

Strategy:
1. Create tables in public schema via Supabase SQL Editor API
2. Seed mock data via REST API (PostgREST)
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# Load .env
from dotenv import load_dotenv

# Try to load from multiple locations
for env_path in [
    Path(__file__).parent.parent / "backend" / ".env",
    Path(__file__).parent.parent / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        break

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ============================================================
# SQL to create tables in public schema
# ============================================================
CREATE_TABLES_SQL = """
-- Dimension: Products
CREATE TABLE IF NOT EXISTS dim_products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    sub_category    VARCHAR(100),
    brand           VARCHAR(100),
    unit_price      NUMERIC(12, 2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Dimension: Customers
CREATE TABLE IF NOT EXISTS dim_customers (
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

-- Fact: Sales
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id         BIGSERIAL PRIMARY KEY,
    order_date      DATE NOT NULL,
    product_id      INTEGER REFERENCES dim_products(product_id),
    customer_id     INTEGER REFERENCES dim_customers(customer_id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12, 2) NOT NULL,
    total_amount    NUMERIC(14, 2) NOT NULL,
    discount        NUMERIC(5, 2) DEFAULT 0,
    channel         VARCHAR(50) DEFAULT 'online',
    payment_method  VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- System Metrics: Hourly Snapshot
CREATE TABLE IF NOT EXISTS hourly_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     VARCHAR(100) NOT NULL UNIQUE,
    value           NUMERIC(18, 4) NOT NULL,
    previous_value  NUMERIC(18, 4),
    change_pct      NUMERIC(8, 4),
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Raw Staging
CREATE TABLE IF NOT EXISTS raw_sales (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(100) DEFAULT 'mock_crawler',
    data            JSONB NOT NULL,
    crawled_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE
);
"""


def execute_sql(sql: str) -> dict:
    """Execute SQL via Supabase SQL API (pg_net or rpc)."""
    # Try using Supabase's built-in SQL execution
    # Method 1: Try rpc/exec_sql
    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        json={"query": sql},
        headers=HEADERS,
        timeout=30,
    )
    if response.status_code == 200:
        return {"success": True, "data": response.json()}

    # Method 2: Try the SQL query endpoint (Supabase Management API)
    # This requires the service role key
    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
        json={"sql_query": sql},
        headers=HEADERS,
        timeout=30,
    )
    if response.status_code == 200:
        return {"success": True, "data": response.json()}

    return {"success": False, "error": response.text, "status": response.status_code}


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists via PostgREST."""
    response = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&limit=0",
        headers=HEADERS,
        timeout=10,
    )
    return response.status_code == 200


def insert_data(table: str, data: list) -> dict:
    """Insert data via PostgREST."""
    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        json=data,
        headers=HEADERS,
        timeout=30,
    )
    if response.status_code in (200, 201):
        return {"success": True, "count": len(data)}
    return {"success": False, "error": response.text[:200], "status": response.status_code}


def get_count(table: str) -> int:
    """Get row count from a table."""
    headers = {**HEADERS, "Prefer": "count=exact"}
    response = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*",
        headers={**headers, "Range": "0-0"},
        timeout=10,
    )
    if response.status_code in (200, 206):
        content_range = response.headers.get("content-range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            if total != "*":
                return int(total)
    return 0


# ============================================================
# Mock Data Generators
# ============================================================

PRODUCTS = [
    {"product_name": "iPhone 15 Pro Max", "category": "Electronics", "sub_category": "Smartphones", "brand": "Apple", "unit_price": 29990000},
    {"product_name": "Samsung Galaxy S24 Ultra", "category": "Electronics", "sub_category": "Smartphones", "brand": "Samsung", "unit_price": 27990000},
    {"product_name": "MacBook Air M3", "category": "Electronics", "sub_category": "Laptops", "brand": "Apple", "unit_price": 32990000},
    {"product_name": "Dell XPS 15", "category": "Electronics", "sub_category": "Laptops", "brand": "Dell", "unit_price": 35990000},
    {"product_name": "Sony WH-1000XM5", "category": "Electronics", "sub_category": "Audio", "brand": "Sony", "unit_price": 7990000},
    {"product_name": "Nike Air Max 90", "category": "Fashion", "sub_category": "Shoes", "brand": "Nike", "unit_price": 3590000},
    {"product_name": "Adidas Ultraboost", "category": "Fashion", "sub_category": "Shoes", "brand": "Adidas", "unit_price": 4290000},
    {"product_name": "Uniqlo Down Jacket", "category": "Fashion", "sub_category": "Clothing", "brand": "Uniqlo", "unit_price": 1990000},
    {"product_name": "Dyson V15 Detect", "category": "Home", "sub_category": "Appliances", "brand": "Dyson", "unit_price": 16990000},
    {"product_name": "Philips Air Fryer", "category": "Home", "sub_category": "Kitchen", "brand": "Philips", "unit_price": 3290000},
    {"product_name": "Logitech MX Master 3S", "category": "Electronics", "sub_category": "Accessories", "brand": "Logitech", "unit_price": 2490000},
    {"product_name": "iPad Pro M4", "category": "Electronics", "sub_category": "Tablets", "brand": "Apple", "unit_price": 28990000},
    {"product_name": "Samsung QLED 65 inch", "category": "Electronics", "sub_category": "TVs", "brand": "Samsung", "unit_price": 24990000},
    {"product_name": "Xiaomi Robot Vacuum", "category": "Home", "sub_category": "Appliances", "brand": "Xiaomi", "unit_price": 8990000},
    {"product_name": "The North Face Jacket", "category": "Fashion", "sub_category": "Clothing", "brand": "The North Face", "unit_price": 5990000},
]

CUSTOMERS = [
    {"customer_name": "Nguyễn Văn An", "email": "an.nguyen@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"customer_name": "Trần Thị Bình", "email": "binh.tran@email.com", "segment": "Standard", "region": "Miền Bắc", "city": "Hà Nội"},
    {"customer_name": "Lê Hoàng Cường", "email": "cuong.le@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"customer_name": "Phạm Minh Đức", "email": "duc.pham@email.com", "segment": "Enterprise", "region": "Miền Trung", "city": "Đà Nẵng"},
    {"customer_name": "Hoàng Thị Em", "email": "em.hoang@email.com", "segment": "Standard", "region": "Miền Bắc", "city": "Hải Phòng"},
    {"customer_name": "Vũ Quang Phú", "email": "phu.vu@email.com", "segment": "Premium", "region": "Miền Nam", "city": "Cần Thơ"},
    {"customer_name": "Đặng Thị Giang", "email": "giang.dang@email.com", "segment": "Enterprise", "region": "Miền Bắc", "city": "Hà Nội"},
    {"customer_name": "Bùi Văn Hải", "email": "hai.bui@email.com", "segment": "Standard", "region": "Miền Trung", "city": "Huế"},
    {"customer_name": "Ngô Thị Lan", "email": "lan.ngo@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"customer_name": "Đỗ Minh Khoa", "email": "khoa.do@email.com", "segment": "Enterprise", "region": "Miền Bắc", "city": "Hà Nội"},
    {"customer_name": "Lý Thị Mai", "email": "mai.ly@email.com", "segment": "Standard", "region": "Miền Trung", "city": "Nha Trang"},
    {"customer_name": "Trịnh Văn Nam", "email": "nam.trinh@email.com", "segment": "Premium", "region": "Miền Nam", "city": "Bình Dương"},
]

CHANNELS = ["online", "offline", "marketplace", "social_media"]
PAYMENT_METHODS = ["credit_card", "bank_transfer", "momo", "zalopay", "cod"]


def generate_sales_records(product_ids: list, customer_ids: list, count: int = 500) -> list:
    """Generate mock sales records."""
    records = []
    utc_now = datetime.now(timezone.utc)

    for _ in range(count):
        product_id = random.choice(product_ids)
        customer_id = random.choice(customer_ids)
        product = PRODUCTS[product_id - 1]  # 1-indexed
        quantity = random.randint(1, 5)
        discount = random.choice([0, 5, 10, 15, 20])
        unit_price = product["unit_price"]
        total_amount = unit_price * quantity * (1 - discount / 100)

        days_ago = random.randint(0, 365)
        seconds_ago = random.randint(0, 86399)
        order_dt = utc_now - timedelta(days=days_ago, seconds=seconds_ago)
        order_date = order_dt.date().isoformat()

        records.append({
            "order_date": order_date,
            "created_at": order_dt.isoformat(),
            "product_id": product_id,
            "customer_id": customer_id,
            "quantity": quantity,
            "unit_price": float(unit_price),
            "total_amount": float(total_amount),
            "discount": float(discount),
            "channel": random.choice(CHANNELS),
            "payment_method": random.choice(PAYMENT_METHODS),
        })
    return records


def main():
    print("=" * 60)
    print("OMNI-REVENUE AGENT - Database Setup")
    print("=" * 60)
    print(f"Supabase URL: {SUPABASE_URL}")

    # Step 1: Check connectivity
    print("\n[1/5] Checking Supabase connectivity...")
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            print("  ✓ Supabase REST API is accessible")
        else:
            print(f"  ✗ Supabase REST API returned {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        sys.exit(1)

    # Step 2: Try to create tables via SQL
    print("\n[2/5] Creating tables...")
    sql_result = execute_sql(CREATE_TABLES_SQL)
    if sql_result.get("success"):
        print("  ✓ Tables created via SQL RPC")
    else:
        print(f"  ⚠ SQL RPC not available (this is normal for new Supabase projects)")
        print(f"    Error: {sql_result.get('error', 'unknown')[:100]}")
        print("  → Please create tables manually via Supabase SQL Editor")
        print("  → Copy the SQL from: database/supabase_schema_public.sql")

        # Check if tables already exist
        tables_exist = True
        for table in ["dim_products", "dim_customers", "fact_sales"]:
            if check_table_exists(table):
                print(f"  ✓ Table '{table}' already exists")
            else:
                print(f"  ✗ Table '{table}' does not exist")
                tables_exist = False

        if not tables_exist:
            print("\n  ⚠ Tables need to be created first!")
            print("  Please run the SQL in database/supabase_schema_public.sql")
            print("  via Supabase Dashboard > SQL Editor")
            sys.exit(1)

    # Step 3: Seed Products
    print("\n[3/5] Seeding products...")
    existing_products = get_count("dim_products")
    if existing_products > 0:
        print(f"  ⚠ dim_products already has {existing_products} rows, skipping")
    else:
        result = insert_data("dim_products", PRODUCTS)
        if result["success"]:
            print(f"  ✓ Inserted {result['count']} products")
        else:
            print(f"  ✗ Insert failed: {result.get('error', '')[:100]}")

    # Step 4: Seed Customers
    print("\n[4/5] Seeding customers...")
    existing_customers = get_count("dim_customers")
    if existing_customers > 0:
        print(f"  ⚠ dim_customers already has {existing_customers} rows, skipping")
    else:
        result = insert_data("dim_customers", CUSTOMERS)
        if result["success"]:
            print(f"  ✓ Inserted {result['count']} customers")
        else:
            print(f"  ✗ Insert failed: {result.get('error', '')[:100]}")

    # Step 5: Seed Sales
    print("\n[5/5] Seeding sales data...")
    existing_sales = get_count("fact_sales")
    if existing_sales > 0:
        print(f"  ⚠ fact_sales already has {existing_sales} rows, skipping")
    else:
        product_ids = list(range(1, len(PRODUCTS) + 1))
        customer_ids = list(range(1, len(CUSTOMERS) + 1))
        sales = generate_sales_records(product_ids, customer_ids, count=500)

        # Insert in batches of 50
        total_inserted = 0
        for i in range(0, len(sales), 50):
            batch = sales[i:i + 50]
            result = insert_data("fact_sales", batch)
            if result["success"]:
                total_inserted += result["count"]
                print(f"  → Batch {i // 50 + 1}: Inserted {result['count']} records")
            else:
                print(f"  ✗ Batch {i // 50 + 1} failed: {result.get('error', '')[:100]}")
                break

        print(f"  ✓ Total inserted: {total_inserted} sales records")

    # Summary
    print(f"\n{'=' * 60}")
    print("SETUP COMPLETE!")
    print(f"  dim_products:   {get_count('dim_products')} rows")
    print(f"  dim_customers:  {get_count('dim_customers')} rows")
    print(f"  fact_sales:     {get_count('fact_sales')} rows")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
