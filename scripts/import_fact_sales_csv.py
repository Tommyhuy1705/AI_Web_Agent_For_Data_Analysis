import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv


def to_float(value: str) -> float:
    v = (value or "").strip()
    if not v:
        return 0.0
    v = v.replace(".", "").replace(",", ".")
    return float(v)


def to_int(value: str) -> int:
    v = (value or "").strip()
    if not v:
        return 0
    return int(v)


def parse_created_at(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return datetime.utcnow().isoformat()
    dt = datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")
    return dt.isoformat()


def load_env() -> tuple[str, str]:
    for env_path in [
        Path(__file__).parent.parent / "backend" / ".env",
        Path(__file__).parent.parent / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break

    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    return supabase_url, service_key


def read_csv_rows(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            row = {
                "order_date": (r.get("order_date", "") or "").strip(),
                "product_id": to_int(r.get("product_id", "0")),
                "customer_id": to_int(r.get("customer_id", "0")),
                "quantity": to_int(r.get("quantity", "0")),
                "unit_price": to_float(r.get("unit_price", "0")),
                "total_amount": to_float(r.get("total_amount", "0")),
                "discount": to_float(r.get("discount", "0")),
                "channel": (r.get("channel", "") or "").strip(),
                "payment_method": (r.get("payment_method", "") or "").strip(),
                "created_at": parse_created_at(r.get("created_at", "")),
            }
            rows.append(row)
    return rows


def get_current_max_sale_id(supabase_url: str, service_key: str) -> int:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    resp = httpx.get(
        f"{supabase_url}/rest/v1/fact_sales?select=sale_id&order=sale_id.desc&limit=1",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        return 0
    data = resp.json()
    if not data:
        return 0
    return int(data[0].get("sale_id", 0))


def get_existing_ids(supabase_url: str, service_key: str, table: str, id_col: str) -> set[int]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    resp = httpx.get(
        f"{supabase_url}/rest/v1/{table}?select={id_col}&limit=5000",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        return set()
    return {int(r[id_col]) for r in resp.json() if r.get(id_col) is not None}


def ensure_missing_dimensions(supabase_url: str, service_key: str, rows: list[dict]) -> None:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    customer_ids = sorted({int(r["customer_id"]) for r in rows})
    product_ids = sorted({int(r["product_id"]) for r in rows})

    existing_customers = get_existing_ids(supabase_url, service_key, "dim_customers", "customer_id")
    existing_products = get_existing_ids(supabase_url, service_key, "dim_products", "product_id")

    missing_customers = [cid for cid in customer_ids if cid not in existing_customers]
    missing_products = [pid for pid in product_ids if pid not in existing_products]

    if missing_customers:
        payload = [
            {
                "customer_id": cid,
                "customer_name": f"Imported Customer {cid}",
                "email": f"imported_customer_{cid}@example.com",
                "segment": "Standard",
                "region": "Unknown",
                "city": "Unknown",
                "country": "Vietnam",
            }
            for cid in missing_customers
        ]
        resp = httpx.post(
            f"{supabase_url}/rest/v1/dim_customers",
            json=payload,
            headers=headers,
            timeout=60,
        )
        if resp.status_code not in (200, 201, 204):
            print(f"ERROR inserting missing customers: {resp.status_code}")
            print(resp.text[:500])
            sys.exit(2)
        print(f"Inserted missing dim_customers: {len(missing_customers)}")

    if missing_products:
        payload = [
            {
                "product_id": pid,
                "product_name": f"Imported Product {pid}",
                "category": "Imported",
                "sub_category": "Imported",
                "brand": "Unknown",
                "unit_price": 0,
            }
            for pid in missing_products
        ]
        resp = httpx.post(
            f"{supabase_url}/rest/v1/dim_products",
            json=payload,
            headers=headers,
            timeout=60,
        )
        if resp.status_code not in (200, 201, 204):
            print(f"ERROR inserting missing products: {resp.status_code}")
            print(resp.text[:500])
            sys.exit(2)
        print(f"Inserted missing dim_products: {len(missing_products)}")


def insert_batches(supabase_url: str, service_key: str, rows: list[dict], batch_size: int = 100) -> None:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        resp = httpx.post(
            f"{supabase_url}/rest/v1/fact_sales",
            json=batch,
            headers=headers,
            timeout=60,
        )
        if resp.status_code not in (200, 201, 204):
            print(f"Batch failed ({i}-{i + len(batch) - 1}): {resp.status_code}")
            print(resp.text[:500])
            sys.exit(2)
        inserted += len(batch)
        print(f"Inserted {inserted}/{len(rows)}")


def main() -> None:
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    csv_path = Path(csv_arg) if csv_arg else Path.home() / "Downloads" / "fact_sales_sample.csv"

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        sys.exit(1)

    supabase_url, service_key = load_env()
    rows = read_csv_rows(csv_path)
    if not rows:
        print("ERROR: No rows to insert")
        sys.exit(1)

    ensure_missing_dimensions(supabase_url, service_key, rows)

    # Avoid duplicate PK and broken DB sequence by assigning fresh sale_id values.
    max_sale_id = get_current_max_sale_id(supabase_url, service_key)
    for i, row in enumerate(rows, start=1):
        row["sale_id"] = max_sale_id + i

    print(f"Loaded {len(rows)} rows from {csv_path}")
    print(f"Assigning sale_id from {max_sale_id + 1} to {max_sale_id + len(rows)}")
    insert_batches(supabase_url, service_key, rows, batch_size=100)
    print("DONE: Import completed")


if __name__ == "__main__":
    main()
