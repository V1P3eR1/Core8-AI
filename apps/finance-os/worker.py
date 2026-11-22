"""Sandbox-only idempotent processor; requires psycopg and approved DATABASE_URL."""
import os

def process_batch(limit=20):
    if os.getenv("APP_ENV", "sandbox") not in {"sandbox", "development", "test"}:
        raise RuntimeError("sandbox only")
    if not (isinstance(limit, int) and 1 <= limit <= 100):
        raise ValueError("limit 1..100")
    import psycopg
    processed = 0
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        with conn.transaction():
            rows = conn.execute("""
                SELECT event_id, organization_id, event_type, source_object_id
                FROM finance_stripe_event_inbox
                WHERE status IN ('received', 'failed')
                  AND attempts < 5
                  AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                ORDER BY received_at, event_id
                FOR UPDATE SKIP LOCKED LIMIT %s
            """, (limit,)).fetchall()
            for event_id, org, event_type, obj_id in rows:
                conn.execute("""
                    INSERT INTO finance_activity
                      (stripe_event_id,organization_id,event_type,source_object_id)
                    VALUES (%s,%s,%s,%s) ON CONFLICT (stripe_event_id) DO NOTHING
                """, (event_id,org,event_type,obj_id))
                conn.execute("""
                    UPDATE finance_stripe_event_inbox
                    SET status='processed',processed_at=now()
                    WHERE event_id=%s
                """, (event_id,))
                processed += 1
    return processed
