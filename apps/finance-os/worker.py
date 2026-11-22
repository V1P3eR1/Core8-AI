"""Sandbox-only idempotent Stripe inbox consumer with bounded retries.

This writes operational activity metadata, not money, invoices or accounting entries.
"""
import os

MAX_ATTEMPTS = 5


def process_batch(limit=20):
    if os.getenv("APP_ENV", "sandbox").lower() not in {"sandbox", "development", "test"}:
        raise RuntimeError("sandbox only")
    if os.getenv("ENABLE_STRIPE_WRITES", "false").lower() != "false":
        raise RuntimeError("Stripe writes forbidden")
    if not (isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= 100):
        raise ValueError("limit 1..100")
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")

    import psycopg

    processed = 0
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.transaction():
            rows = conn.execute("""
                SELECT event_id, organization_id, event_type, source_object_id
                FROM finance_stripe_event_inbox
                WHERE status IN ('received', 'failed')
                  AND attempts < %s
                  AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                ORDER BY received_at, event_id
                FOR UPDATE SKIP LOCKED LIMIT %s
            """, (MAX_ATTEMPTS, limit)).fetchall()
            for event_id, org, event_type, obj_id in rows:
                try:
                    # Nested transaction is a savepoint: one failed insert
                    # cannot poison the surrounding PostgreSQL transaction.
                    with conn.transaction():
                        conn.execute("""
                            INSERT INTO finance_activity
                              (stripe_event_id,organization_id,event_type,source_object_id)
                            VALUES (%s,%s,%s,%s) ON CONFLICT (stripe_event_id) DO NOTHING
                        """, (event_id, org, event_type, obj_id))
                        conn.execute("""
                            UPDATE finance_stripe_event_inbox
                            SET status='processed', processed_at=now(),
                                next_attempt_at=NULL
                            WHERE event_id=%s
                        """, (event_id,))
                except Exception:
                    # Do not persist exception strings, which may contain PII.
                    # Retry with bounded exponential backoff, then dead-letter.
                    conn.execute("""
                        UPDATE finance_stripe_event_inbox
                        SET attempts=attempts+1,
                            status=CASE WHEN attempts+1 >= %s THEN 'dead' ELSE 'failed' END,
                            next_attempt_at=CASE WHEN attempts+1 >= %s THEN NULL
                               ELSE now() + (LEAST(POWER(2, attempts), 60) * INTERVAL '1 minute') END
                        WHERE event_id=%s
                    """, (MAX_ATTEMPTS, MAX_ATTEMPTS, event_id))
                    continue
                processed += 1
    return processed
