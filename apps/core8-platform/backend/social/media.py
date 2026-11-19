"""Media storage, Instagram spec validation and signed, time-limited public URLs.

Files are stored under SOCIAL_MEDIA_DIR (outside the platform's unsigned
/media static mount). Meta must fetch media by URL, so publishing hands it a
URL signed with an HMAC and an expiry (default 2 h). After the publication
reaches a final state the worker revokes the grant (`revoke_grant`).

Specs below are from the IG User Media reference (checked 2026-10-27):
image JPEG ≤ 8 MB, aspect 4:5 … 1.91:1, width 320–1440 px; reels MP4/MOV
H.264/HEVC, ≤ 300 MB, 3 s – 15 min, 9:16 recommended; story video ≤ 100 MB,
3–60 s; story image JPEG ≤ 8 MB 9:16 recommended; carousel 2–20 items.
"""

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import time

from PIL import Image

from security.subprocess_env import shell_minimal

from .config import scfg
from .db import execute, fetch_all, fetch_one, jdump, new_id

ALLOWED_MIME = {
    "image/jpeg": ("image", "jpg"),
    "image/png": ("image", "png"),   # accepted for upload; converted to JPEG for publishing
    "video/mp4": ("video", "mp4"),
    "video/quicktime": ("video", "mov"),
}

SPECS = {
    "image": {"max_bytes": 8 * 1024 * 1024, "min_ratio": 0.8, "max_ratio": 1.91,
              "min_width": 320, "max_width": 1440, "formats": ("JPEG",)},
    "reel": {"max_bytes": 300 * 1024 * 1024, "min_s": 3, "max_s": 15 * 60},
    "story_video": {"max_bytes": 100 * 1024 * 1024, "min_s": 3, "max_s": 60},
    "story_image": {"max_bytes": 8 * 1024 * 1024},
    "carousel": {"min_items": 2, "max_items": 20},
    "caption_max": 2200, "hashtags_max": 30, "alt_text_max": 1000,
}


def media_dir() -> str:
    os.makedirs(scfg.media_dir, exist_ok=True)
    return scfg.media_dir


def _ffprobe(path: str) -> dict:
    """Duration/dimensions via ffprobe if installed; otherwise {}."""
    exe = shutil.which("ffprobe")
    if not exe:
        return {}
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
            capture_output=True, text=True, timeout=30, env=shell_minimal(), check=False,
        ).stdout
        data = json.loads(out or "{}")
        v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {
            "width": v.get("width"), "height": v.get("height"),
            "duration_s": float(data.get("format", {}).get("duration") or 0) or None,
            "codec": v.get("codec_name"),
        }
    except Exception:
        return {}


def probe(path: str, media_type: str) -> dict:
    if media_type == "image":
        with Image.open(path) as im:
            return {"width": im.width, "height": im.height, "format": im.format,
                    "mode": im.mode, "duration_s": None}
    return _ffprobe(path)


def validate_for_instagram(asset: dict, usage: str) -> dict:
    """usage: image | carousel_item | reel | story. Returns {ok, problems[], warnings[]}."""
    problems, warnings = [], []
    size = asset.get("bytes") or 0
    w, h = asset.get("width"), asset.get("height")
    mt = asset.get("media_type")
    dur = asset.get("duration_s")
    fmt = (asset.get("mime") or "").lower()

    if usage in ("image", "carousel_item") and mt == "image":
        s = SPECS["image"]
        if fmt != "image/jpeg":
            problems.append("Instagram מקבל JPEG בלבד לתמונות — יש להמיר ל-JPEG")
        if size > s["max_bytes"]:
            problems.append("קובץ תמונה גדול מ-8MB")
        if w and h:
            ratio = w / h
            if not (s["min_ratio"] - 0.01 <= ratio <= s["max_ratio"] + 0.01):
                problems.append(f"יחס תמונה {ratio:.2f} מחוץ לטווח 4:5 … 1.91:1")
            if w < s["min_width"]:
                warnings.append("רוחב קטן מ-320px — אינסטגרם יגדיל את התמונה")
            if w > s["max_width"]:
                warnings.append("רוחב גדול מ-1440px — אינסטגרם יקטין את התמונה")
        else:
            warnings.append("לא ניתן לקרוא מידות")
    elif usage in ("reel", "carousel_item") and mt == "video":
        s = SPECS["reel"]
        if size > s["max_bytes"]:
            problems.append("וידאו גדול מ-300MB")
        if dur is not None and not (s["min_s"] <= dur <= s["max_s"]):
            problems.append(f"אורך {dur:.0f}s מחוץ לטווח 3s–15min")
        if dur is None:
            warnings.append("ffprobe לא זמין — אורך/קודק לא אומתו; יש לוודא MP4 H.264/AAC")
        if w and h and abs((w / h) - 9 / 16) > 0.05:
            warnings.append("יחס לא 9:16 — מומלץ 1080×1920 לרילס")
    elif usage == "story":
        if mt == "video":
            s = SPECS["story_video"]
            if size > s["max_bytes"]:
                problems.append("וידאו סטורי גדול מ-100MB")
            if dur is not None and not (s["min_s"] <= dur <= s["max_s"]):
                problems.append(f"אורך סטורי {dur:.0f}s מחוץ לטווח 3–60s")
        else:
            if fmt != "image/jpeg":
                problems.append("סטורי תמונה חייב להיות JPEG")
            if size > SPECS["story_image"]["max_bytes"]:
                problems.append("תמונת סטורי גדולה מ-8MB")
    elif usage == "reel" and mt != "video":
        problems.append("רילס דורש קובץ וידאו אמיתי — תסריט אינו וידאו")
    elif usage == "image" and mt != "image":
        problems.append("פוסט תמונה דורש קובץ תמונה")
    return {"ok": not problems, "problems": problems, "warnings": warnings, "usage": usage}


async def save_upload(data: bytes, original_name: str, mime: str, ownership: str = "owner_upload",
                      permission_note: str | None = None, is_demo: int = 0,
                      alt_text: str | None = None, caption: str | None = None,
                      brief: str | None = None) -> dict:
    if mime not in ALLOWED_MIME:
        raise ValueError(f"סוג קובץ לא נתמך: {mime}")
    if not data:
        raise ValueError("קובץ ריק")
    if len(data) > scfg.max_upload_bytes:
        raise ValueError("קובץ גדול מדי")
    media_type, ext = ALLOWED_MIME[mime]
    asset_id = new_id()
    filename = f"{asset_id}.{ext}"
    path = os.path.join(media_dir(), filename)
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    try:
        meta = probe(path, media_type)
    except Exception:
        meta = {}
    # Verify the declared mime matches the bytes for images.
    if media_type == "image" and meta.get("format") not in ("JPEG", "PNG"):
        os.remove(path)
        raise ValueError("התוכן אינו תמונת JPEG/PNG תקינה")
    asset = {
        "id": asset_id, "filename": filename, "original_name": original_name[:200],
        "media_type": media_type, "mime": mime, "bytes": len(data),
        "width": meta.get("width"), "height": meta.get("height"),
        "duration_s": meta.get("duration_s"), "sha256": sha, "ownership": ownership,
        "permission_note": permission_note, "alt_text": alt_text, "caption": caption,
        "brief": brief, "is_demo": is_demo,
    }
    default_usage = "image" if media_type == "image" else "reel"
    asset["spec_check"] = jdump(validate_for_instagram(asset, default_usage))
    await execute(
        """INSERT INTO sm_assets (id, filename, original_name, media_type, mime, bytes, width, height,
             duration_s, sha256, ownership, permission_note, alt_text, caption, brief, spec_check, is_demo)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (asset_id, filename, asset["original_name"], media_type, mime, len(data), asset["width"],
         asset["height"], asset["duration_s"], sha, ownership, permission_note, alt_text, caption,
         brief, asset["spec_check"], is_demo))
    return await get_asset(asset_id)


async def get_asset(asset_id: str) -> dict | None:
    row = await fetch_one("SELECT * FROM sm_assets WHERE id=?", (asset_id,))
    if row:
        row["spec_check"] = json.loads(row["spec_check"]) if row.get("spec_check") else None
    return row


async def list_assets(include_demo: bool = True) -> list[dict]:
    rows = await fetch_all("SELECT * FROM sm_assets ORDER BY created_at DESC")
    out = []
    for r in rows:
        if not include_demo and r["is_demo"]:
            continue
        r["spec_check"] = json.loads(r["spec_check"]) if r.get("spec_check") else None
        out.append(r)
    return out


async def delete_asset(asset_id: str) -> bool:
    row = await fetch_one("SELECT filename FROM sm_assets WHERE id=?", (asset_id,))
    if not row:
        return False
    path = os.path.join(media_dir(), row["filename"])
    if os.path.exists(path):
        os.remove(path)
    await execute("DELETE FROM sm_assets WHERE id=?", (asset_id,))
    return True


def asset_path(asset: dict) -> str:
    return os.path.join(media_dir(), asset["filename"])


# ── Signed public URLs (what Meta fetches) ──────────────────────────────────

def _sig(asset_id: str, exp: int) -> str:
    msg = f"{asset_id}:{exp}".encode()
    return hmac.new(scfg.media_signing_key.encode(), msg, hashlib.sha256).hexdigest()[:40]


def signed_url(asset_id: str, ttl_seconds: int | None = None) -> str:
    exp = int(time.time()) + (ttl_seconds or scfg.media_url_ttl_seconds)
    base = scfg.media_base_url.rstrip("/")
    # The platform's MEDIA_BASE_URL ends with /media; the signed route lives under /api/social.
    if base.endswith("/media"):
        base = base[: -len("/media")]
    return f"{base}/api/social/media-public/{asset_id}?exp={exp}&sig={_sig(asset_id, exp)}"


def verify_signature(asset_id: str, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_sig(asset_id, exp), sig or "")


async def is_revoked(asset_id: str) -> bool:
    """Revocations are persisted so the API process honours what the worker revoked."""
    row = await fetch_one("SELECT asset_id FROM sm_media_grants WHERE asset_id=? AND revoked_at IS NOT NULL", (asset_id,))
    return row is not None


async def revoke_grant(asset_id: str) -> None:
    """Stop serving an asset publicly (called once a publication is final)."""
    await execute("INSERT INTO sm_media_grants (asset_id, revoked_at) VALUES (?, datetime('now')) "
                  "ON CONFLICT(asset_id) DO UPDATE SET revoked_at=datetime('now')", (asset_id,))


async def restore_grant(asset_id: str) -> None:
    await execute("DELETE FROM sm_media_grants WHERE asset_id=?", (asset_id,))
