# Database Migrations

SQL migration scripts for Supabase schema management.

## Migration Order

| File | Description |
|---|---|
| `001_initial_schema.sql` | Initial schema: raw_staging, analytics_mart, system_metrics |
| `002_public_schema.sql` | Public schema: dim_customers, dim_products, fact_sales, hourly_snapshot, competitor_prices |

## Apply Migrations

```bash
# Via psql
psql $SUPABASE_DATABASE_URL -f database/migrations/001_initial_schema.sql
psql $SUPABASE_DATABASE_URL -f database/migrations/002_public_schema.sql

# Via Supabase CLI
supabase db push
```
