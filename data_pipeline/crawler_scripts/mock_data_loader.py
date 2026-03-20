"""
Mock Data Loader - Đổ dữ liệu giả lập vào raw_staging.raw_sales (JSONB)
Sử dụng asyncpg để kết nối Supabase PostgreSQL.
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

import asyncpg

# Supabase connection string từ environment variable
DATABASE_URL = os.getenv(
    "SUPABASE_DATABASE_URL",
    "postgresql://postgres:your_password@db.your_project.supabase.co:5432/postgres"
)

# ============================================================
# Mock Data Generators
# ============================================================

PRODUCTS = [
    {"name": "iPhone 15 Pro Max", "category": "Electronics", "sub_category": "Smartphones", "brand": "Apple", "price": 29990000},
    {"name": "Samsung Galaxy S24 Ultra", "category": "Electronics", "sub_category": "Smartphones", "brand": "Samsung", "price": 27990000},
    {"name": "MacBook Air M3", "category": "Electronics", "sub_category": "Laptops", "brand": "Apple", "price": 32990000},
    {"name": "Dell XPS 15", "category": "Electronics", "sub_category": "Laptops", "brand": "Dell", "price": 35990000},
    {"name": "Sony WH-1000XM5", "category": "Electronics", "sub_category": "Audio", "brand": "Sony", "price": 7990000},
    {"name": "Nike Air Max 90", "category": "Fashion", "sub_category": "Shoes", "brand": "Nike", "price": 3590000},
    {"name": "Adidas Ultraboost", "category": "Fashion", "sub_category": "Shoes", "brand": "Adidas", "price": 4290000},
    {"name": "Uniqlo Down Jacket", "category": "Fashion", "sub_category": "Clothing", "brand": "Uniqlo", "price": 1990000},
    {"name": "Dyson V15 Detect", "category": "Home", "sub_category": "Appliances", "brand": "Dyson", "price": 16990000},
    {"name": "Philips Air Fryer", "category": "Home", "sub_category": "Kitchen", "brand": "Philips", "price": 3290000},
    {"name": "Logitech MX Master 3S", "category": "Electronics", "sub_category": "Accessories", "brand": "Logitech", "price": 2490000},
    {"name": "iPad Pro M4", "category": "Electronics", "sub_category": "Tablets", "brand": "Apple", "price": 28990000},
    {"name": "Samsung QLED 65 inch", "category": "Electronics", "sub_category": "TVs", "brand": "Samsung", "price": 24990000},
    {"name": "Xiaomi Robot Vacuum", "category": "Home", "sub_category": "Appliances", "brand": "Xiaomi", "price": 8990000},
    {"name": "The North Face Jacket", "category": "Fashion", "sub_category": "Clothing", "brand": "The North Face", "price": 5990000},
]

CUSTOMERS = [
    {"name": "Nguyễn Văn An", "email": "an.nguyen@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"name": "Trần Thị Bình", "email": "binh.tran@email.com", "segment": "Standard", "region": "Miền Bắc", "city": "Hà Nội"},
    {"name": "Lê Hoàng Cường", "email": "cuong.le@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"name": "Phạm Minh Đức", "email": "duc.pham@email.com", "segment": "Enterprise", "region": "Miền Trung", "city": "Đà Nẵng"},
    {"name": "Hoàng Thị Em", "email": "em.hoang@email.com", "segment": "Standard", "region": "Miền Bắc", "city": "Hải Phòng"},
    {"name": "Vũ Quang Phú", "email": "phu.vu@email.com", "segment": "Premium", "region": "Miền Nam", "city": "Cần Thơ"},
    {"name": "Đặng Thị Giang", "email": "giang.dang@email.com", "segment": "Enterprise", "region": "Miền Bắc", "city": "Hà Nội"},
    {"name": "Bùi Văn Hải", "email": "hai.bui@email.com", "segment": "Standard", "region": "Miền Trung", "city": "Huế"},
    {"name": "Ngô Thị Lan", "email": "lan.ngo@email.com", "segment": "Premium", "region": "Miền Nam", "city": "TP.HCM"},
    {"name": "Đỗ Minh Khoa", "email": "khoa.do@email.com", "segment": "Enterprise", "region": "Miền Bắc", "city": "Hà Nội"},
    {"name": "Lý Thị Mai", "email": "mai.ly@email.com", "segment": "Standard", "region": "Miền Trung", "city": "Nha Trang"},
    {"name": "Trịnh Văn Nam", "email": "nam.trinh@email.com", "segment": "Premium", "region": "Miền Nam", "city": "Bình Dương"},
]

CHANNELS = ["online", "offline", "marketplace", "social_media"]
PAYMENT_METHODS = ["credit_card", "bank_transfer", "momo", "zalopay", "cod"]


def generate_mock_sale_record() -> Dict[str, Any]:
    """Sinh một bản ghi bán hàng giả lập dưới dạng JSONB."""
    product = random.choice(PRODUCTS)
    customer = random.choice(CUSTOMERS)
    quantity = random.randint(1, 5)
    discount = random.choice([0, 5, 10, 15, 20])
    unit_price = product["price"]
    total_amount = unit_price * quantity * (1 - discount / 100)

    # Random date trong 12 tháng gần nhất
    days_ago = random.randint(0, 365)
    order_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    order_time = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"

    return {
        "order_id": f"ORD-{random.randint(100000, 999999)}",
        "order_date": order_date,
        "order_time": order_time,
        "product": {
            "name": product["name"],
            "category": product["category"],
            "sub_category": product["sub_category"],
            "brand": product["brand"],
            "unit_price": unit_price,
        },
        "customer": {
            "name": customer["name"],
            "email": customer["email"],
            "segment": customer["segment"],
            "region": customer["region"],
            "city": customer["city"],
        },
        "quantity": quantity,
        "discount_pct": discount,
        "total_amount": total_amount,
        "channel": random.choice(CHANNELS),
        "payment_method": random.choice(PAYMENT_METHODS),
        "status": random.choice(["completed", "completed", "completed", "pending", "cancelled"]),
    }


def generate_batch(batch_size: int = 100) -> List[Dict[str, Any]]:
    """Sinh một batch dữ liệu mock."""
    return [generate_mock_sale_record() for _ in range(batch_size)]


# ============================================================
# Database Operations
# ============================================================

async def insert_raw_sales(pool: asyncpg.Pool, records: List[Dict[str, Any]]) -> int:
    """Insert batch dữ liệu vào raw_staging.raw_sales."""
    inserted = 0
    async with pool.acquire() as conn:
        for record in records:
            await conn.execute(
                """
                INSERT INTO raw_staging.raw_sales (source, data)
                VALUES ($1, $2::jsonb)
                """,
                "mock_crawler",
                json.dumps(record, ensure_ascii=False),
            )
            inserted += 1
    return inserted


async def get_raw_sales_count(pool: asyncpg.Pool) -> int:
    """Đếm số bản ghi trong raw_staging.raw_sales."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM raw_staging.raw_sales")
        return row["cnt"]


async def main():
    """Main entry point - Đổ mock data vào Supabase."""
    print("=" * 60)
    print("OMNI-REVENUE AGENT - Mock Data Loader")
    print("=" * 60)

    # Kết nối Supabase
    print(f"\n[1/4] Connecting to Supabase...")
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
        print("  ✓ Connected successfully!")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        print(f"  → Please set SUPABASE_DATABASE_URL environment variable")
        return

    # Kiểm tra schema tồn tại
    print(f"\n[2/4] Checking schema...")
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT COUNT(*) as cnt FROM information_schema.schemata WHERE schema_name = 'raw_staging'"
            )
            if result["cnt"] == 0:
                print("  ✗ Schema raw_staging not found. Please run supabase_schema.sql first!")
                return
            print("  ✓ Schema raw_staging exists")
    except Exception as e:
        print(f"  ✗ Schema check failed: {e}")
        return

    # Sinh mock data
    total_records = 500
    batch_size = 100
    print(f"\n[3/4] Generating {total_records} mock sales records...")

    all_records = generate_batch(total_records)
    print(f"  ✓ Generated {len(all_records)} records")

    # Insert vào database
    print(f"\n[4/4] Inserting into raw_staging.raw_sales...")
    total_inserted = 0
    for i in range(0, len(all_records), batch_size):
        batch = all_records[i:i + batch_size]
        inserted = await insert_raw_sales(pool, batch)
        total_inserted += inserted
        print(f"  → Batch {i // batch_size + 1}: Inserted {inserted} records")

    # Kiểm tra kết quả
    count = await get_raw_sales_count(pool)
    print(f"\n{'=' * 60}")
    print(f"✓ DONE! Total records in raw_staging.raw_sales: {count}")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
