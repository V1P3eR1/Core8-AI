"""Tool risk policy — the single source of truth for what a tool may do (issue #11, TECH_DEBT X8).

Every registered tool must have an explicit risk class here (enforced by tests); a tool that is
missing is treated as EXTERNAL, the strictest class.

Risk classes, least to most sensitive:
  read         — reads tenant data, no side effects
  write        — creates/updates the tenant's own internal records (CRM, calendar, docs, plans)
  destructive  — deletes or cancels internal records
  external     — acts outside Core8 or on a live third-party account (publishing, OAuth,
                 paid generation)

Approval (APPROVAL_MODE):
  manual — every tool call needs human approval
  smart  — destructive and external calls need approval (default)
  off    — external calls STILL need approval: sensitive actions are never unattended
A call that needs approval when no human approver is connected is refused, never run.
"""

READ, WRITE, DESTRUCTIVE, EXTERNAL = "read", "write", "destructive", "external"
_ORDER = [READ, WRITE, DESTRUCTIVE, EXTERNAL]

TOOL_RISK: dict[str, str] = {
    # CRM
    "list_leads": READ, "search_leads": READ, "get_lead": READ,
    "create_lead": WRITE, "update_lead": WRITE, "add_note": WRITE,
    # Calendar (internal DB)
    "list_events": READ, "find_free_slot": READ,
    "create_event": WRITE, "update_event": WRITE, "delete_event": DESTRUCTIVE,
    # Design docs
    "list_design_docs": READ, "list_design_projects": READ, "read_design_doc": READ,
    "write_design_doc": WRITE, "create_feature_spec": WRITE, "delete_design_doc": DESTRUCTIVE,
    # Instagram planning (internal)
    "list_content_plans": READ, "get_content_plan": READ, "read_plan_artifact": READ,
    "create_content_plan": WRITE, "update_content_plan": WRITE, "save_plan_artifact": WRITE,
    "run_niche_finder": WRITE, "run_viral_blueprint": WRITE, "run_caption_generator": WRITE,
    "run_hashtag_formula": WRITE, "run_content_schedule": WRITE, "run_monetization_map": WRITE,
    "run_automation_setup": WRITE,
    # Instagram account / publishing (live third-party account)
    "list_ig_accounts": READ, "list_scheduled_posts": READ, "list_media_assets": READ,
    "get_account_insights": READ, "get_post_insights": READ,
    "connect_instagram": EXTERNAL, "queue_post": EXTERNAL,
    "cancel_scheduled_post": DESTRUCTIVE,
    "generate_post_image": EXTERNAL,  # paid third-party generation
}

# Tools whose results contain content written by people outside the operator (lead notes and
# form data, Instagram data, web/LLM-generated artifacts). Their output is wrapped as untrusted.
UNTRUSTED_OUTPUT_TOOLS = {
    "list_leads", "search_leads", "get_lead",
    "get_account_insights", "get_post_insights", "list_scheduled_posts",
    "read_plan_artifact", "get_content_plan", "read_design_doc",
}


def risk_of(tool_name: str) -> str:
    return TOOL_RISK.get(tool_name, EXTERNAL)


def at_least(tool_name: str, level: str) -> bool:
    return _ORDER.index(risk_of(tool_name)) >= _ORDER.index(level)


def needs_approval(tool_name: str, mode: str, tainted: bool = False) -> bool:
    """Whether a call must be approved by a human. `tainted` is set once untrusted content in
    this run was flagged as a possible prompt injection: from then on every side-effecting call
    needs approval, whatever the mode."""
    risk = risk_of(tool_name)
    if risk == EXTERNAL:
        return True
    if tainted and risk != READ:
        return True
    if mode == "manual":
        return True
    if mode == "off":
        return False
    return risk == DESTRUCTIVE  # smart (default; unknown modes behave as smart)
