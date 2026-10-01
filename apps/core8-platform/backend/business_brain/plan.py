"""AI Transformation Plan draft generator (DESIGN.md §5).

Built only from Brain values and opportunity analysis. Contains no pricing (CORE8-002 owns
that) and no fabricated metrics: every gap is listed under information gaps.
"""

from collections import OrderedDict

from business_brain.questionnaire import Questionnaire

PHASES = ["Now", "Next", "Later"]


def _fmt_list(items) -> str:
    return ", ".join(items) if items else "—"


def build_plan(qn: Questionnaire, values: dict, analysis: dict) -> dict:
    opps = analysis["opportunities"]
    company = values.get("exec.company_name") or "The client"
    industry = values.get("exec.industry")
    employees = values.get("exec.employee_count")
    active_titles = [qn.module(m)["title"] for m in analysis["active_modules"]]
    by_phase = {p: [o for o in opps if o["phase"] == p] for p in PHASES}

    profile_bits = [b for b in (industry, f"~{employees:g} employees" if isinstance(employees, (int, float)) else None) if b]
    summary = (
        f"{company}{' (' + ', '.join(profile_bits) + ')' if profile_bits else ''} completed Core8 discovery "
        f"covering: {_fmt_list(active_titles)}. "
        f"{len(opps)} AI opportunities were identified — {len(by_phase['Now'])} for now, "
        f"{len(by_phase['Next'])} next and {len(by_phase['Later'])} later."
    )
    if opps:
        top = opps[0]
        summary += (
            f" Highest priority: '{top['pain_statement']}' in {top['module_title']} "
            f"→ {top['recommended_agent']['capability']} ({top['phase']})."
        )
    goals = values.get("exec.goals") or []

    # Pain map
    pain_map = OrderedDict()
    for o in opps:
        pain_map.setdefault(o["module_title"], []).append(
            {"pain": o["pain_statement"], "impact": o["business_impact"], "phase": o["phase"]}
        )

    # Current-state workflows
    workflows = []
    for mid in analysis["active_modules"]:
        m = qn.module(mid)
        wf = values.get(f"{mid}.current_workflow")
        workflows.append({
            "module": m["title"],
            "workflow": wf,
            "roles": values.get(f"{mid}.people_involved") or [],
            "systems": values.get(f"{mid}.systems_used") or [],
            "known": bool(wf),
        })

    # AI workforce (one row per agent role)
    workforce = OrderedDict()
    for o in opps:
        a = o["recommended_agent"]
        row = workforce.setdefault(a["agent_role"], {
            "agent_role": a["agent_role"], "capability": a["capability"], "availability": a["availability"],
            "modules": [], "addresses": [], "earliest_phase": o["phase"],
        })
        if o["module_title"] not in row["modules"]:
            row["modules"].append(o["module_title"])
        row["addresses"].append(o["pain_statement"])
        if PHASES.index(o["phase"]) < PHASES.index(row["earliest_phase"]):
            row["earliest_phase"] = o["phase"]

    integrations = sorted({s for o in opps for s in o["required_integrations"]}, key=str.lower)

    phases = [
        {"phase": p, "items": [
            {"module": o["module_title"], "pain": o["pain_statement"], "agent_role": o["recommended_agent"]["agent_role"],
             "complexity": o["implementation_complexity"], "priority_score": o["priority_score"]}
            for o in by_phase[p]]}
        for p in PHASES
    ]

    kpis = [{"module": o["module_title"], "kpi": o["kpi"]["value"], "source": o["kpi"]["source"]} for o in opps]
    kpis = list({(k["module"], k["kpi"]): k for k in kpis}.values())

    risks = [{
        "module": o["module_title"], "pain": o["pain_statement"], "risk": o["risk_approval_level"]["risk"],
        "human_approval_required": o["risk_approval_level"]["human_approval_required"],
        "approval_steps": o["risk_approval_level"]["approval_steps"],
    } for o in opps]
    global_controls = values.get("exec.never_without_approval") or []
    sensitive = [c for c in (values.get("exec.sensitive_data_categories") or []) if c != "none"]

    gaps = []
    for o in opps:
        gaps.extend(o["open_questions"])
        gaps.extend(o["assumptions"])
    for pain in analysis["unmapped_pains"]:
        gaps.append(f"Executive pain '{pain}' is not mapped to a discovery module yet — run the relevant module.")
    gaps = list(dict.fromkeys(gaps))

    content = {
        "executive_summary": {"text": summary, "goals": goals},
        "business_pain_map": pain_map,
        "current_state_workflows": workflows,
        "recommended_ai_workforce": list(workforce.values()),
        "integrations_required": integrations,
        "implementation_phases": phases,
        "kpis": kpis,
        "risks_and_approval_controls": {
            "per_opportunity": risks, "never_without_approval": global_controls,
            "sensitive_data_categories": sensitive,
        },
        "information_gaps_and_assumptions": gaps,
        "notes": ["Draft generated from discovery data. No pricing and no ROI estimates are included."],
    }
    return content


def render_markdown(content: dict, company: str) -> str:
    L = [f"# AI Transformation Plan — {company} (draft)", ""]
    es = content["executive_summary"]
    L += ["## Executive summary", "", es["text"], ""]
    if es["goals"]:
        L += ["**Business goals:** " + "; ".join(es["goals"]), ""]

    L += ["## Business pain map", ""]
    for module, pains in content["business_pain_map"].items():
        L.append(f"**{module}**")
        L += [f"- {p['pain']} — impact: {p['impact'] or 'not rated'}; phase: {p['phase']}" for p in pains]
        L.append("")

    L += ["## Current-state workflow map", ""]
    for w in content["current_state_workflows"]:
        L.append(f"**{w['module']}** — {w['workflow'] or '_not described yet_'}")
        L.append(f"  - Roles: {_fmt_list(w['roles'])} · Systems: {_fmt_list(w['systems'])}")
    L.append("")

    L += ["## Recommended AI workforce", "", "| Agent | Capability | Status | Areas | Earliest phase |", "|---|---|---|---|---|"]
    for a in content["recommended_ai_workforce"]:
        L.append(f"| `{a['agent_role']}` | {a['capability']} | {a['availability']} | {', '.join(a['modules'])} | {a['earliest_phase']} |")
    L.append("")

    L += ["## Integrations required", "", _fmt_list(content["integrations_required"]), ""]

    L += ["## Implementation phases", ""]
    for p in content["implementation_phases"]:
        L.append(f"### {p['phase']}")
        L += [f"- {i['module']}: {i['pain']} → `{i['agent_role']}` (complexity {i['complexity']}, priority {i['priority_score']})"
              for i in p["items"]] or ["- —"]
        L.append("")

    L += ["## KPIs / success criteria", ""]
    L += [f"- {k['module']}: {k['kpi']}{' _(suggested)_' if k['source'] == 'default_suggestion' else ''}" for k in content["kpis"]] or ["- —"]
    L.append("")

    r = content["risks_and_approval_controls"]
    L += ["## Risks & approval controls", ""]
    if r["never_without_approval"]:
        L.append("**Never without human approval:** " + "; ".join(r["never_without_approval"]))
    if r["sensitive_data_categories"]:
        L.append("**Sensitive data categories:** " + ", ".join(r["sensitive_data_categories"]))
    for x in r["per_opportunity"]:
        approval = "human approval required" if x["human_approval_required"] else "standard approval gate"
        L.append(f"- {x['module']} / {x['pain']}: risk {x['risk']}, {approval}")
    L.append("")

    L += ["## Information gaps / assumptions", ""]
    L += [f"- {g}" for g in content["information_gaps_and_assumptions"]] or ["- None"]
    L += ["", "---", "_" + " ".join(content["notes"]) + "_", ""]
    return "\n".join(L)
