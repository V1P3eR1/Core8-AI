"""Loader for the canonical business rules (markdown files in this folder).

Both the runtime agents and the Claude Code skill point here, so there is
exactly one copy of the rules.
"""

import os
from functools import lru_cache

RULES_DIR = os.path.dirname(__file__)
RULE_FILES = ("brand_voice", "research_workflow", "content_workflow",
              "publishing_rules", "weekly_analysis")


@lru_cache(maxsize=None)
def load_rule(name: str) -> str:
    path = os.path.join(RULES_DIR, f"{name}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def all_rules() -> dict[str, str]:
    return {n: load_rule(n) for n in RULE_FILES}
