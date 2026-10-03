"""AI Opportunity Engine v1 — deterministic, explainable scoring (DESIGN.md §4).

Input is the Brain's current view of the discovery answers (so accepted corrections apply).
No ROI, savings or prices are computed: missing inputs become explicit assumptions and
open questions.
"""

import uuid

from business_brain.questionnaire import Questionnaire, active_modules

COMPLEXITY = ["low", "medium", "high"]
RISK = ["low", "medium", "high"]
IMPACT_POINTS = {"critical": 25, "high": 15, "medium": 5, "low": -5}
SUITABILITY_POINTS = {"high": 15, "medium": 5, "low": -10, "unknown": 0}
SENSITIVITY_RISK = {"public": "low", "internal": "low", "confidential": "medium", "restricted": "high"}


def brain_answers(facts: list[dict]) -> dict:
    """Map question id → answer from active questionnaire/correction facts."""
    out = {}
    for f in facts:
        if f["fact_key"].startswith("q:") and isinstance(f["value"], dict) and "answer" in f["value"]:
            out[f["fact_key"][2:]] = f["value"]["answer"]
    return out


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _suitability(volume, hours, error_rate) -> tuple[str, list[str]]:
    if volume is None and hours is None:
        return "unknown", ["Automation suitability unknown: no volume or time-spent data."]
    points, why = 0, []
    if volume is not None:
        if volume >= 200:
            points += 2; why.append(f"High monthly volume ({volume:g}) favours automation.")
        elif volume >= 30:
            points += 1; why.append(f"Moderate monthly volume ({volume:g}).")
        else:
            why.append(f"Low monthly volume ({volume:g}) limits automation value.")
    if hours is not None:
        if hours >= 15:
            points += 2; why.append(f"{hours:g} staff hours/week spent — significant manual effort.")
        elif hours >= 4:
            points += 1; why.append(f"{hours:g} staff hours/week spent.")
        else:
            why.append(f"Only {hours:g} staff hours/week spent.")
    if error_rate is not None and error_rate >= 5:
        points += 1; why.append(f"Error/rework rate of {error_rate:g}% suggests a repeatable process worth standardising.")
    level = "high" if points >= 3 else "medium" if points >= 1 else "low"
    return level, why


def _module_pains(qn: Questionnaire, values: dict, module_id: str) -> list[str]:
    return list(values.get(f"{module_id}.bottlenecks") or [])


def _map_exec_pain(qn: Questionnaire, pain: str, active: list[str]) -> str | None:
    text = pain.lower()
    # Prefer active modules, then any module.
    for pool in (active, [m["id"] for m in qn.modules]):
        for mid in pool:
            if any(k in text for k in qn.module(mid).get("pain_keywords", [])):
                return mid
    return None


def build_opportunity(qn: Questionnaire, values: dict, module_id: str, pain: str, origin: str) -> dict:
    m = qn.module(module_id)
    cap = m["capability"]
    p = f"{module_id}."
    answered_module = any(k.startswith(p) for k in values)
    rationale, assumptions, questions = [], [], []

    # Volume / effort
    volume = _num(values.get(p + "monthly_volume"))
    volume_source = "module"
    if volume is None and m.get("volume_question"):
        volume = _num(values.get(m["volume_question"]))
        volume_source = "executive intake"
    if volume is None:
        questions.append(f"What is the monthly volume for {m['title']}?")
        assumptions.append("Monthly volume not provided — impact of automation cannot be sized yet.")
    hours = _num(values.get(p + "hours_per_week"))
    if hours is None:
        questions.append(f"How many staff hours per week go into {m['title']}?")
    error_rate = _num(values.get(p + "error_rate_pct"))

    suitability, s_why = _suitability(volume, hours, error_rate)
    rationale.extend(s_why)

    impact = values.get(p + "business_impact")
    if impact is None:
        questions.append(f"What is the business impact of '{pain}'?")
        assumptions.append("Business impact not rated — treated as neutral for prioritisation.")

    current_process = values.get(p + "current_workflow")
    if not current_process:
        questions.append(f"Describe the current {m['title']} workflow.")

    # Integrations
    systems = list(values.get(p + "systems_used") or [])
    crm = values.get(p + "crm_system")
    if crm and crm not in systems:
        systems.append(crm)
    if not systems:
        questions.append(f"Which systems are used for {m['title']}? (needed to scope integrations)")

    # Complexity
    c = COMPLEXITY.index(cap["base_complexity"])
    data_level = values.get(p + "data_sensitivity", "internal")
    if len(systems) > 2:
        c += 1; rationale.append(f"{len(systems)} systems to integrate increases complexity.")
    if data_level in ("confidential", "restricted"):
        c += 1; rationale.append(f"{data_level.capitalize()} data increases complexity (access controls, review).")
    complexity = COMPLEXITY[min(c, 2)]

    # Risk / approvals
    risk = cap["risk"]
    sens_risk = SENSITIVITY_RISK.get(data_level, "low")
    if RISK.index(sens_risk) > RISK.index(risk):
        risk = sens_risk
        rationale.append(f"Risk raised to {risk} because the area handles {data_level} data.")
    approvals = list(values.get(p + "required_approvals") or [])
    global_approvals = list(values.get("exec.never_without_approval") or [])
    approval_required = bool(approvals) or cap["risk"] == "high" or module_id == "finance"
    if module_id == "finance":
        rationale.append("Finance: workflow support only — no autonomous financial transactions in v1.")

    # KPI
    kpi_answer = values.get(p + "kpi")
    kpi = {"value": kpi_answer, "source": "client"} if kpi_answer else {"value": cap["default_kpi"], "source": "default_suggestion"}
    if not kpi_answer:
        assumptions.append(f"KPI is a Core8 default suggestion for {m['title']}; confirm with the client.")

    # Priority
    score = 50
    if impact in IMPACT_POINTS:
        score += IMPACT_POINTS[impact]; rationale.append(f"Business impact rated '{impact}' ({IMPACT_POINTS[impact]:+d}).")
    score += SUITABILITY_POINTS[suitability]
    if SUITABILITY_POINTS[suitability]:
        rationale.append(f"Automation suitability '{suitability}' ({SUITABILITY_POINTS[suitability]:+d}).")
    if complexity == "high":
        score -= 15; rationale.append("High implementation complexity (-15).")
    elif complexity == "medium":
        score -= 5; rationale.append("Medium implementation complexity (-5).")
    if risk == "high":
        score -= 10; rationale.append("High risk — requires approval controls (-10).")
    available = cap["availability"] == "available"
    if not available:
        score -= 5; rationale.append(f"Agent '{cap['agent_role']}' is planned, not yet built (-5).")
    score = max(0, min(100, score))

    if score >= 70 and complexity != "high" and available:
        phase = "Now"
    elif score >= 45:
        phase = "Next"
    else:
        phase = "Later"
    rationale.append(f"Priority {score}/100 → phase {phase}.")
    if not answered_module:
        assumptions.append(f"{m['title']} module not answered yet; recommendation based on executive intake only.")

    return {
        "id": str(uuid.uuid4()),
        "module": module_id,
        "module_title": m["title"],
        "origin": origin,
        "pain_statement": pain,
        "current_process": current_process,
        "frequency_volume": {"monthly": volume, "source": volume_source if volume is not None else None},
        "manual_effort_hours_per_week": hours,
        "business_impact": impact,
        "automation_suitability": suitability,
        "recommended_agent": {
            "agent_role": cap["agent_role"], "capability": cap["capability"], "availability": cap["availability"],
        },
        "required_integrations": systems,
        "implementation_complexity": complexity,
        "risk_approval_level": {
            "risk": risk,
            "human_approval_required": approval_required,
            "approval_steps": approvals,
            "global_never_without_approval": global_approvals,
        },
        "kpi": kpi,
        "phase": phase,
        "priority_score": score,
        "rationale": rationale,
        "assumptions": assumptions,
        "open_questions": questions,
    }


def analyse(qn: Questionnaire, values: dict) -> dict:
    """Return {opportunities, unmapped_pains, active_modules}."""
    active = active_modules(qn, values)
    opps, unmapped = [], []
    seen = set()
    for mid in active:
        for pain in _module_pains(qn, values, mid):
            key = (mid, pain.strip().lower())
            if key not in seen:
                seen.add(key)
                opps.append(build_opportunity(qn, values, mid, pain, origin=f"{mid}.bottlenecks"))
    for pain in values.get("exec.top_pains") or []:
        mid = _map_exec_pain(qn, pain, active)
        if mid is None:
            unmapped.append(pain)
            continue
        key = (mid, pain.strip().lower())
        if key not in seen:
            seen.add(key)
            opps.append(build_opportunity(qn, values, mid, pain, origin="exec.top_pains"))
    opps.sort(key=lambda o: (-o["priority_score"], o["module"]))
    return {"opportunities": opps, "unmapped_pains": unmapped, "active_modules": active}

