"""Deterministic provenance and freshness regression coverage."""
import unittest
from datetime import datetime, timedelta, timezone

from snapshot_metadata import metadata, MetadataError

NOW = datetime(2026, 11, 23, 10, 30, tzinfo=timezone.utc)


class SnapshotMetadataTests(unittest.TestCase):
    def test_current_repo_snapshot_is_recent_at_render_only(self):
        src = {"source": "github_repo_open_prs", "coverage": "partial",
               "generated_at": (NOW - timedelta(minutes=3)).isoformat()}
        obj = metadata(src, NOW)
        self.assertEqual(obj["freshness"], "recent_at_render")
        self.assertEqual(obj["coverage"], "partial")
        self.assertEqual(obj["observed_at"], "2026-11-23 10:27 UTC")

    def test_older_snapshot_warns(self):
        src = {"source": "github_current_head_pr",
               "generated_at": (NOW - timedelta(hours=3)).isoformat()}
        self.assertEqual(metadata(src, NOW)["freshness"], "stale_at_render")

    def test_missing_timestamp_is_never_current(self):
        self.assertEqual(metadata({}, NOW)["freshness"], "unknown")
        self.assertEqual(metadata({"demo": True}, NOW)["freshness"], "synthetic")

    def test_utc_conversion(self):
        src = {"generated_at": "2026-11-23T12:25:00+02:00"}
        self.assertEqual(metadata(src, NOW)["observed_at"], "2026-11-23 10:25 UTC")

    def test_future_timestamp_rejected(self):
        src = {"generated_at": (NOW + timedelta(minutes=10)).isoformat()}
        with self.assertRaisesRegex(MetadataError, "future"):
            metadata(src, NOW)

    def test_naive_timestamp_and_unknown_source_rejected(self):
        for src in [{"generated_at": "2026-11-23T10:25:00"},
                    {"generated_at": "not-a-date"},
                    {"source": "https://evil.example/secret"},
                    {"coverage": "magically_complete"},
                    {"demo": True, "source": "github_repo_open_prs"},
                    {"demo": True, "coverage": "complete"}]:
            with self.assertRaises(MetadataError):
                metadata(src, NOW)

    def test_clock_must_be_timezone_aware(self):
        with self.assertRaises(MetadataError):
            metadata({"generated_at": "2026-11-23T10:25:00Z"},
                     datetime(2026, 11, 23, 10, 30))

if __name__ == "__main__":
    unittest.main()
