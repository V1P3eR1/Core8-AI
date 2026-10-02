import pytest

from business_brain.questionnaire import (
    AnswerError, active_modules, load_questionnaire, next_question, progress, validate_answer,
)
from tests.conftest import INTAKE

qn = load_questionnaire()


def test_definition_has_all_twelve_modules_and_template_fields():
    ids = [m["id"] for m in qn.modules]
    assert ids == ["sales_crm", "customer_service", "office_admin", "email_calendar", "marketing_social",
                   "operations", "finance", "hr", "management_bi", "knowledge_docs", "integrations_it",
                   "security_compliance"]
    for m in qn.modules:
        fields = {q["field"] for q in m["questions"]}
        assert {"current_workflow", "people_involved", "systems_used", "monthly_volume", "hours_per_week",
                "bottlenecks", "error_rate_pct", "business_impact", "desired_outcome", "required_approvals",
                "data_sensitivity", "kpi"} <= fields
        # Sensitivity is asked first so facts are labelled correctly from the start.
        assert m["questions"][0]["field"] == "data_sensitivity"


def test_no_modules_active_before_intake():
    assert active_modules(qn, {}) == []
    assert next_question(qn, {})["id"] == "exec.company_name"


def test_focus_areas_activate_only_selected_modules():
    assert active_modules(qn, {"exec.focus_areas": ["office_admin"]}) == ["office_admin"]


def test_volume_triggers_activate_modules_without_focus():
    answers = {"exec.focus_areas": [], "exec.monthly_support_requests": 50, "exec.monthly_leads": 0}
    assert active_modules(qn, answers) == ["customer_service"]


def test_sensitive_data_activates_security_module():
    assert "security_compliance" in active_modules(qn, {"exec.sensitive_data_categories": ["health"]})
    assert "security_compliance" not in active_modules(qn, {"exec.sensitive_data_categories": ["none"]})


def test_large_stack_activates_integrations():
    stack = ["A", "B", "C", "D", "E"]
    assert "integrations_it" in active_modules(qn, {"exec.software_stack": stack})
    assert "integrations_it" not in active_modules(qn, {"exec.software_stack": stack[:4]})


def test_next_question_moves_into_active_module_after_intake():
    answers = dict(INTAKE)
    nq = next_question(qn, answers)
    assert nq["module"] == "sales_crm" and nq["id"] == "sales_crm.data_sensitivity"


def test_progress_counts_required_across_active_modules():
    p = progress(qn, dict(INTAKE))
    assert not p["complete"]
    assert "sales_crm.bottlenecks" in p["missing_required"]
    assert "office_admin.admin_tasks" in p["missing_required"]
    assert not any(q.startswith("hr.") for q in p["missing_required"])


@pytest.mark.parametrize("qid,value", [
    ("exec.employee_count", "forty"),
    ("exec.employee_count", -1),
    ("exec.employee_count", True),
    ("exec.focus_areas", ["sales_crm", "not_a_module"]),
    ("exec.top_pains", ["a", "b", "c", "d"]),
    ("exec.company_name", ""),
    ("sales_crm.business_impact", "huge"),
    ("exec.company_name", "x" * 5000),
])
def test_invalid_answers_rejected(qid, value):
    with pytest.raises(AnswerError):
        validate_answer(qn.questions[qid], value)


def test_list_answers_are_trimmed_and_empty_items_dropped():
    assert validate_answer(qn.questions["exec.goals"], ["  grow ", "", "hire"]) == ["grow", "hire"]


def test_every_text_and_option_is_translated():
    for q in qn.questions.values():
        for lc in ("en", "he", "ru"):
            assert q["text_i18n"][lc].strip(), (q["id"], lc)
            for o in q.get("options", []):
                assert q["option_labels"][o][lc].strip(), (q["id"], o, lc)
    for m in qn.modules:
        assert all(m["title_i18n"][lc].strip() for lc in ("en", "he", "ru"))


def test_missing_translation_fails_loading(tmp_path):
    import json
    from business_brain.questionnaire import _DEFINITION_PATH
    raw = json.load(open(_DEFINITION_PATH, encoding="utf-8"))
    del raw["intake"]["questions"][0]["text"]["ru"]
    bad = tmp_path / "q.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="missing translations"):
        load_questionnaire.__wrapped__(str(bad))
