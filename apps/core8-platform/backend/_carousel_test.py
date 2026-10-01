import os, sys, asyncio, tempfile, sqlite3

sys.stdout.reconfigure(encoding="utf-8")
TMP_DB = os.path.join(tempfile.gettempdir(), "core8_carousel_test.db")
os.environ["DB_PATH"] = TMP_DB
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pre-seed the temp DB with the OLD scheduled_posts schema (no media_urls,
# CHECK only allows image/reel). Simulates a pre-existing DB before migration.
conn = sqlite3.connect(TMP_DB)
conn.executescript("""
    CREATE TABLE scheduled_posts (
        id            TEXT PRIMARY KEY,
        plan_id       TEXT,
        post_type     TEXT NOT NULL CHECK(post_type IN ('image','reel')),
        media_url     TEXT NOT NULL,
        caption       TEXT,
        scheduled_for TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK(status IN ('pending','publishing','published','failed','cancelled')),
        ig_media_id   TEXT,
        attempts      INTEGER NOT NULL DEFAULT 0,
        last_error    TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );
    INSERT INTO scheduled_posts (id, plan_id, post_type, media_url, scheduled_for, caption)
    VALUES ('legacy-1', NULL, 'image', 'https://example.com/legacy.jpg',
            '2020-01-01 00:00:00', 'legacy');
""")
conn.commit()
conn.close()

import aiosqlite
from database import init_db, get_db
from tools import instagram_api
from tools.instagram_accounts import save_ig_account
from tools.instagram_publish import (
    register_instagram_publish_tools, queue_post, list_scheduled_posts,
    claim_due_posts,
)
from scheduler import run_scheduler_tick

PAST = "2020-01-01T00:00:00"


async def fake_publish(**kw):
    fake_publish.calls.append(kw)
    return f"ig_media_FAKE_{len(fake_publish.calls)}"
fake_publish.calls = []


async def main():
    register_instagram_publish_tools()
    await init_db()  # triggers the carousel migration on the pre-seeded table

    # 1. Migration preserved the legacy row + added media_urls column
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("PRAGMA table_info(scheduled_posts)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        assert "media_urls" in cols, "migration did not add media_urls"
        async with db.execute("SELECT post_type, caption FROM scheduled_posts WHERE id='legacy-1'") as cur:
            row = await cur.fetchone()
        assert row and row["post_type"] == "image" and row["caption"] == "legacy"
    print("migration: legacy row preserved, media_urls column added")

    # 2. New CHECK accepts 'carousel' (would have raised on old schema)
    async with get_db() as db:
        await db.execute(
            "INSERT INTO scheduled_posts (id, post_type, media_url, scheduled_for) "
            "VALUES ('chk', 'carousel', 'x', '2020-01-01 00:00:00')")
        await db.execute("DELETE FROM scheduled_posts WHERE id='chk'")
        await db.commit()
    print("migration: post_type CHECK now accepts 'carousel'")

    # 3. queue_post carousel — happy path
    urls = [f"https://example.com/c{i}.jpg" for i in range(3)]
    r = await queue_post(PAST, media_urls=urls, post_type="carousel", caption="hi")
    assert r.get("status") == "pending", r
    carousel_id = r["id"]
    print("queue_post (carousel): inserted")

    # 4. validation
    assert "error" in await queue_post(PAST, media_urls=["only-one"], post_type="carousel")
    assert "error" in await queue_post(PAST, media_urls=["x"] * 11, post_type="carousel")
    assert "error" in await queue_post(PAST, media_urls="not-a-list", post_type="carousel")  # type: ignore
    print("queue_post (carousel): rejects <2, >10, non-list")

    # 5. image post still works (no media_urls)
    img = await queue_post(PAST, media_url="https://example.com/i.jpg", post_type="image")
    assert img.get("status") == "pending", img
    print("queue_post (image): unchanged path still works")

    # 6. list_scheduled_posts parses media_urls
    lst = await list_scheduled_posts(status="pending")
    car = next(p for p in lst if p["id"] == carousel_id)
    assert isinstance(car["media_urls"], list) and len(car["media_urls"]) == 3
    img_row = next(p for p in lst if p["id"] == img["id"])
    assert img_row["media_urls"] is None
    print("list_scheduled_posts: media_urls parsed (list for carousel, null for image)")

    # 7. Scheduler routes carousel through the carousel branch
    await save_ig_account("17841400000000000", "112233", "testuser",
                          "EAABfake_token", None)
    instagram_api.publish_post = fake_publish
    await run_scheduler_tick(lambda: False)
    carousel_calls = [c for c in fake_publish.calls if c["post_type"] == "carousel"]
    assert len(carousel_calls) == 1, f"expected 1 carousel call, got {carousel_calls}"
    assert isinstance(carousel_calls[0]["media_urls"], list)
    assert len(carousel_calls[0]["media_urls"]) == 3
    assert carousel_calls[0].get("media_url") is None
    print("scheduler tick: carousel routed with media_urls list (not media_url)")

    pub_ids = {p["id"] for p in await list_scheduled_posts(status="published")}
    assert carousel_id in pub_ids, "carousel was not marked published"
    print("scheduler tick: carousel marked published")

    # 8. App boots
    from main import app
    assert app is not None
    print("main app imports cleanly")

    print("\nCAROUSEL OK")


asyncio.run(main())
