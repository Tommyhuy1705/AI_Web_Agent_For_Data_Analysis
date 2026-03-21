"""
Test Script: Dashboard Refresh with New Data
Thêm 50 bản ghi fact_sales giả để test dashboard tự động cập nhật sau 2 phút (dbt scheduler).
"""
import psycopg2
import random
from datetime import datetime, timezone

DB_URL = "postgresql://postgres.qunhqqnmsqiahsrneqcy:wT7rEtRsQ6id5Q9x@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres"

def add_test_sales(count=50):
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # Lấy danh sách product_id và customer_id hợp lệ
    cursor.execute("SELECT product_id FROM dim_products LIMIT 50")
    product_ids = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT customer_id FROM dim_customers LIMIT 50")
    customer_ids = [r[0] for r in cursor.fetchall()]

    # Lấy max sale_id hiện tại
    cursor.execute("SELECT MAX(sale_id) FROM fact_sales")
    max_id = cursor.fetchone()[0] or 1000

    now = datetime.now(timezone.utc)
    channels = ["online", "retail", "wholesale", "direct"]
    payments = ["credit_card", "bank_transfer", "cash", "e-wallet"]

    inserted = 0
    for i in range(count):
        sale_id = max_id + i + 1
        product_id = random.choice(product_ids)
        customer_id = random.choice(customer_ids)
        quantity = random.randint(1, 10)
        unit_price = random.uniform(100000, 5000000)
        discount = random.uniform(0, 0.2)
        total_amount = quantity * unit_price * (1 - discount)

        cursor.execute("""
            INSERT INTO fact_sales 
            (sale_id, order_date, product_id, customer_id, quantity, unit_price, total_amount, discount, channel, payment_method, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sale_id) DO NOTHING
        """, (
            sale_id, now.date(), product_id, customer_id,
            quantity, round(unit_price, 2), round(total_amount, 2),
            round(discount, 4), random.choice(channels), random.choice(payments), now
        ))
        inserted += cursor.rowcount

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM fact_sales")
    total = cursor.fetchone()[0]
    print(f"✓ Inserted {inserted} new records. Total fact_sales: {total}")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    add_test_sales(50)
    print("✓ Dashboard refresh test data ready. Wait 2 minutes for dbt scheduler to run.")
