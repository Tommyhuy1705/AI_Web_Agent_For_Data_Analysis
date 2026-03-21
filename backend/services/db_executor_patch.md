# Bug Fix: upsert_via_rest() 409 Conflict

## Problem
`upsert_via_rest()` in `db_executor.py` uses POST with `resolution=merge-duplicates` header,
but Supabase returns HTTP 409 conflict when a unique constraint exists on `metric_name` column
in `hourly_snapshot` table.

## Root Cause
Supabase PostgREST requires the `on_conflict` query parameter to be specified in the URL
for upsert to work correctly with unique constraints.

## Fix Applied (Workaround)
Use PATCH (update) instead of POST (insert) when record already exists:
1. Try PATCH first: `PATCH /rest/v1/{table}?metric_name=eq.{value}`
2. If no record found (204 with empty body), fall back to POST (insert)

## Permanent Fix Recommendation
Update `upsert_via_rest()` in `db_executor.py`:
```python
# Add on_conflict to URL
response = await client.post(
    f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=metric_name",
    json=data,
    headers=headers,
)
```
Or use the PATCH approach for explicit update semantics.
