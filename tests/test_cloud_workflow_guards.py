#!/usr/bin/env python3
"""Offline regression guards for Core8 handoff cloud workflow wiring.

These checks read repository files only; no GitHub/Notion API, tokens or AI calls.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / ".github/workflows/core8-sync.yml"
CLAUDE = ROOT / ".github/workflows/claude-issues.yml"
BRIDGE = ROOT / "tools/handoff/bridge.py"


class CloudWorkflowGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync = SYNC.read_text(encoding="utf-8")
        cls.claude = CLAUDE.read_text(encoding="utf-8")
        cls.bridge = BRIDGE.read_text(encoding="utf-8")

    def test_sync_has_explicit_disabled_by_default_gate(self):
        self.assertIn("vars.CORE8_SYNC_ENABLED == 'true'", self.sync)
        self.assertIn("github.ref == 'refs/heads/main'", self.sync)
        self.assertIn("default: false", self.sync)

    def test_sync_is_serialized_and_has_separate_environment(self):
        self.assertIn("group: core8-notion-sync", self.sync)
        self.assertIn("cancel-in-progress: false", self.sync)
        self.assertIn("environment: core8-sync", self.sync)
        self.assertIn("NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}", self.sync)

    def test_sync_default_dryrun_does_not_apply(self):
        self.assertIn('python tools/handoff/bridge.py sync --apply', self.sync)
        self.assertIn('python tools/handoff/bridge.py sync\n', self.sync)
        self.assertIn('APPLY: ${{ github.event_name == \'schedule\' || inputs.apply }}', self.sync)

    def test_paid_claude_gate_and_isolation(self):
        self.assertIn("vars.CORE8_CLAUDE_ENABLED == 'true'", self.claude)
        self.assertIn("environment: core8-claude", self.claude)
        self.assertIn("CORE8_APPROVER_ID", self.claude)
        self.assertIn("ANTHROPIC_API_KEY", self.claude)

    def test_bridge_requires_private_approval_and_public_export(self):
        self.assertIn("selected(page, 'Decision') == 'Approved'", self.bridge)
        self.assertIn("props.get('Public export', {}).get('checkbox') is True", self.bridge)
        self.assertIn("bool(props.get('Approval evidence', {}).get('url'))", self.bridge)

    def test_bridge_dryrun_never_calls_writes(self):
        self.assertIn("if self.apply:", self.bridge)
        self.assertIn("would_create_issue", self.bridge)


if __name__ == "__main__":
    unittest.main()
