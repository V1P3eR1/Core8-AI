"""Trusted presentation metadata for read-only GitHub CI snapshots.

The dashboard is a static artifact, never a continuously refreshed monitor.
This module rejects fabricated freshness/coverage claims and deliberately
does not inspect customer or private Notion task material.
"""
from datetime import datetime, timezone
import re

MAX_AGE_MINUTES = 15
SOURCES = {
    "github_current_head_pr": "בדיקת PR בודד",
    "github_repo_open_prs": "סקירת PRs פתוחים",
    "github_repo_observer": "ניטור מאגר GitHub",
}


class MetadataError(ValueError):
    pass


def metadata(snapshot, now=None):
    if not isinstance(snapshot, dict):
        raise MetadataError("invalid_snapshot")
    demo = snapshot.get("demo") is True
    source = snapshot.get("source")
    if source is not None and source not in SOURCES:
        raise MetadataError("unknown_source")
    coverage = snapshot.get("coverage")
    if coverage not in (None, "complete", "partial"):
        raise MetadataError("invalid_coverage")
    if demo and source is not None:
        raise MetadataError("conflicting_demo_and_live")
    if demo and coverage is not None:
        raise MetadataError("demo_cannot_claim_coverage")
    raw = snapshot.get("generated_at")
    if raw is None:
        return {
            "source_label": "נתוני הדגמה" if demo else "מקור שלא אומת",
            "observed_at": None,
            "freshness": "synthetic" if demo else "unknown",
            "coverage": coverage,
        }
    if not isinstance(raw, str) or len(raw) > 40:
        raise MetadataError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise MetadataError("invalid_timestamp") from None
    if parsed.tzinfo is None:
        raise MetadataError("timezone_missing")
    parsed = parsed.astimezone(timezone.utc)
    clock = now or datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise MetadataError("invalid_clock")
    seconds = (clock - parsed).total_seconds()
    if seconds < -120:
        raise MetadataError("future_timestamp")
    freshness = "synthetic" if demo else ("recent_at_render" if seconds <= MAX_AGE_MINUTES * 60
                                          else "stale_at_render")
    return {
        "source_label": ("נתוני הדגמה" if demo else SOURCES.get(source, "GitHub CI")),
        "observed_at": parsed.strftime("%Y-%m-%d %H:%M UTC"),
        "freshness": freshness,
        "coverage": coverage,
    }
