"""Data-driven discovery questionnaire: loading, validation, branching and progress.

The questionnaire is defined in questionnaire_v1.json. This module only interprets it —
adding a module or question is a JSON change, not a code change.
"""

import copy
import json
import os
from dataclasses import dataclass
from functools import lru_cache

from business_brain.schema import FACT_CATEGORIES, SENSITIVITY_LEVELS

_DEFINITION_PATH = os.path.join(os.path.dirname(__file__), "questionnaire_v1.json")

QUESTION_TYPES = {"text", "long_text", "number", "boolean", "single_choice", "multi_choice", "list"}
MAX_TEXT = 4000
MAX_LIST_ITEMS = 50
INTAKE_DOMAIN = "general"


class AnswerError(ValueError):
    pass


@dataclass(frozen=True)
class Questionnaire:
    version: str
    title: str
    intake: dict
    modules: list[dict]          # expanded: each module has "questions"
    questions: dict[str, dict]   # id -> question (with "module" and "domain")

    def module(self, module_id: str) -> dict | None:
        return next((m for m in self.modules if m["id"] == module_id), None)

    def public_definition(self) -> dict:
        """The definition as served to clients (no internal routing hints)."""
        return {
            "version": self.version,
            "title": self.title,
            "intake": _strip(self.intake),
            "modules": [
                {**_strip(m), "capability": {k: m["capability"][k] for k in ("agent_role", "availability", "capability")}}
                for m in self.modules
            ],
        }


def _strip(section: dict) -> dict:
    return {
        "id": section["id"],
        "title": section["title"],
        "questions": [
            {k: q[k] for k in ("id", "text", "type", "required", "options", "max_items") if k in q}
            for q in section["questions"]
        ],
    }


@lru_cache(maxsize=1)
def load_questionnaire(path: str = _DEFINITION_PATH) -> Questionnaire:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    questions: dict[str, dict] = {}
    intake = {"id": raw["intake"]["id"], "title": raw["intake"]["title"], "questions": []}
    for q in raw["intake"]["questions"]:
        q = {**q, "module": raw["intake"]["id"], "domain": INTAKE_DOMAIN}
        intake["questions"].append(q)
        questions[q["id"]] = q

    modules = []
    for m in raw["modules"]:
        module = {k: v for k, v in m.items() if k != "extra_questions"}
        module["questions"] = []
        for tmpl in raw["module_template"] + m.get("extra_questions", []):
            q = copy.deepcopy(tmpl)
            field = q.pop("field")
            q["id"] = f"{m['id']}.{field}"
            q["field"] = field
            q["module"] = m["id"]
            q["domain"] = m["id"]
            module["questions"].append(q)
            questions[q["id"]] = q
        modules.append(module)

    qn = Questionnaire(raw["version"], raw["title"], intake, modules, questions)
    _validate_definition(qn)
    return qn


def _validate_definition(qn: Questionnaire) -> None:
    for qid, q in qn.questions.items():
        if q["type"] not in QUESTION_TYPES:
            raise ValueError(f"{qid}: unknown type {q['type']}")
        if q["type"] in ("single_choice", "multi_choice") and not q.get("options"):
            raise ValueError(f"{qid}: choice question without options")
        if q["maps_to"]["category"] not in FACT_CATEGORIES:
            raise ValueError(f"{qid}: unknown category {q['maps_to']['category']}")
        if q.get("sensitivity", "internal") not in SENSITIVITY_LEVELS:
            raise ValueError(f"{qid}: unknown sensitivity")
    for m in qn.modules:
        for cond in m["activation"]["any"]:
            if cond["question"] not in qn.questions:
                raise ValueError(f"{m['id']}: activation references unknown question {cond['question']}")
        if m.get("volume_question") and m["volume_question"] not in qn.questions:
            raise ValueError(f"{m['id']}: unknown volume_question")


# ── Answer validation ────────────────────────────────────────────────────────

def _clean_text(value, qid: str) -> str:
    if not isinstance(value, str):
        raise AnswerError(f"{qid}: expected text")
    value = value.strip()
    if len(value) > MAX_TEXT:
        raise AnswerError(f"{qid}: text longer than {MAX_TEXT} characters")
    return value


def validate_answer(q: dict, value):
    """Return the normalised value or raise AnswerError."""
    qid, t = q["id"], q["type"]
    if t in ("text", "long_text"):
        value = _clean_text(value, qid)
        if q.get("required") and not value:
            raise AnswerError(f"{qid}: answer is required")
        return value
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AnswerError(f"{qid}: expected a number")
        if value < 0:
            raise AnswerError(f"{qid}: must be zero or positive")
        return value
    if t == "boolean":
        if not isinstance(value, bool):
            raise AnswerError(f"{qid}: expected true/false")
        return value
    if t == "single_choice":
        if value not in q["options"]:
            raise AnswerError(f"{qid}: must be one of {q['options']}")
        return value
    if t in ("multi_choice", "list"):
        if not isinstance(value, list):
            raise AnswerError(f"{qid}: expected a list")
        if t == "multi_choice":
            bad = [v for v in value if v not in q["options"]]
            if bad:
                raise AnswerError(f"{qid}: invalid options {bad}")
            value = list(dict.fromkeys(value))
        else:
            value = [v for v in (_clean_text(v, qid) for v in value) if v]
        limit = q.get("max_items", MAX_LIST_ITEMS)
        if len(value) > limit:
            raise AnswerError(f"{qid}: at most {limit} items")
        if q.get("required") and not value:
            raise AnswerError(f"{qid}: answer is required")
        return value
    raise AnswerError(f"{qid}: unsupported type")


# ── Branching ────────────────────────────────────────────────────────────────

def _condition_met(cond: dict, answers: dict) -> bool:
    if cond["question"] not in answers:
        return False
    a, op, v = answers[cond["question"]], cond["op"], cond.get("value")
    if op == "answered":
        return a not in (None, "", [])
    if op == "includes":
        return isinstance(a, list) and v in a
    if op == "includes_any":
        return isinstance(a, list) and any(x in a for x in v)
    if op == "gt":
        return isinstance(a, (int, float)) and not isinstance(a, bool) and a > v
    if op == "equals":
        return a == v
    if op == "count_gte":
        return isinstance(a, list) and len(a) >= v
    raise ValueError(f"unknown activation operator {op}")


def active_modules(qn: Questionnaire, answers: dict) -> list[str]:
    return [m["id"] for m in qn.modules if any(_condition_met(c, answers) for c in m["activation"]["any"])]


def applicable_questions(qn: Questionnaire, answers: dict) -> list[dict]:
    """Intake questions, then questions of active modules, in definition order."""
    result = list(qn.intake["questions"])
    for mid in active_modules(qn, answers):
        result.extend(qn.module(mid)["questions"])
    return result


def next_question(qn: Questionnaire, answers: dict) -> dict | None:
    """First unanswered required question; then optional ones; None when done."""
    applicable = applicable_questions(qn, answers)
    for required in (True, False):
        for q in applicable:
            if bool(q.get("required")) == required and q["id"] not in answers:
                return q
    return None


def progress(qn: Questionnaire, answers: dict) -> dict:
    applicable = applicable_questions(qn, answers)
    required = [q["id"] for q in applicable if q.get("required")]
    answered_required = [qid for qid in required if qid in answers]
    return {
        "required_total": len(required),
        "required_answered": len(answered_required),
        "missing_required": [qid for qid in required if qid not in answers],
        "optional_unanswered": [q["id"] for q in applicable if not q.get("required") and q["id"] not in answers],
        "complete": len(answered_required) == len(required),
    }
