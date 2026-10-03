"""Data-driven discovery questionnaire: loading, validation, branching and progress.

The questionnaire is defined in questionnaire.json. This module only interprets it —
adding a module, question or language is a JSON change, not a code change.

Texts are localised ({"en": ..., "he": ..., "ru": ...}). Internally `text`/`title` hold the
English canonical string (used for Brain facts and agent context); `*_i18n` hold all locales.
Option values are stable codes; only their labels are localised.
"""

import copy
import json
import os
from dataclasses import dataclass
from functools import lru_cache

from business_brain.schema import FACT_CATEGORIES, SENSITIVITY_LEVELS

_DEFINITION_PATH = os.path.join(os.path.dirname(__file__), "questionnaire.json")

QUESTION_TYPES = {"text", "long_text", "number", "boolean", "single_choice", "multi_choice", "list"}
MAX_TEXT = 4000
MAX_LIST_ITEMS = 50
INTAKE_DOMAIN = "general"
DEFAULT_LOCALE = "en"
RTL_LOCALES = {"he", "ar"}


class AnswerError(ValueError):
    pass


@dataclass(frozen=True)
class Questionnaire:
    version: str
    locales: list[str]
    title_i18n: dict
    intake: dict
    modules: list[dict]          # expanded: each module has "questions"
    questions: dict[str, dict]   # id -> question (with "module" and "domain")

    def module(self, module_id: str) -> dict | None:
        return next((m for m in self.modules if m["id"] == module_id), None)

    def resolve_locale(self, lang: str | None) -> str:
        return lang if lang in self.locales else DEFAULT_LOCALE

    def public_definition(self, lang: str | None = None) -> dict:
        """The definition as served to clients, in one locale (no internal routing hints)."""
        lang = self.resolve_locale(lang)
        return {
            "version": self.version,
            "locale": lang,
            "direction": "rtl" if lang in RTL_LOCALES else "ltr",
            "available_locales": self.locales,
            "title": self.title_i18n[lang],
            "intake": localize_section(self.intake, lang),
            "modules": [
                {**localize_section(m, lang),
                 "capability": {k: m["capability"][k] for k in ("agent_role", "availability", "capability")}}
                for m in self.modules
            ],
        }


def localize_question(q: dict | None, lang: str) -> dict | None:
    if q is None:
        return None
    out = {k: q[k] for k in ("id", "type", "required", "options", "max_items", "module") if k in q}
    out["text"] = q["text_i18n"][lang]
    if "option_labels" in q:
        out["option_labels"] = {o: q["option_labels"][o][lang] for o in q["options"]}
    return out


def localize_section(section: dict, lang: str) -> dict:
    return {
        "id": section["id"],
        "title": section["title_i18n"][lang],
        "questions": [localize_question(q, lang) for q in section["questions"]],
    }


def _canonicalize(q: dict) -> dict:
    q["text_i18n"] = q["text"]
    q["text"] = q["text_i18n"][DEFAULT_LOCALE]
    return q


@lru_cache(maxsize=1)
def load_questionnaire(path: str = _DEFINITION_PATH) -> Questionnaire:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    questions: dict[str, dict] = {}
    intake = {"id": raw["intake"]["id"], "title_i18n": raw["intake"]["title"],
              "title": raw["intake"]["title"][DEFAULT_LOCALE], "questions": []}
    for q in raw["intake"]["questions"]:
        q = _canonicalize({**copy.deepcopy(q), "module": raw["intake"]["id"], "domain": INTAKE_DOMAIN})
        intake["questions"].append(q)
        questions[q["id"]] = q

    modules = []
    for m in raw["modules"]:
        module = {k: v for k, v in m.items() if k != "extra_questions"}
        module["title_i18n"] = m["title"]
        module["title"] = m["title"][DEFAULT_LOCALE]
        module["questions"] = []
        for tmpl in raw["module_template"] + m.get("extra_questions", []):
            q = copy.deepcopy(tmpl)
            field = q.pop("field")
            q["id"] = f"{m['id']}.{field}"
            q["field"] = field
            q["module"] = m["id"]
            q["domain"] = m["id"]
            module["questions"].append(_canonicalize(q))
            questions[q["id"]] = q
        modules.append(module)

    qn = Questionnaire(raw["version"], raw["locales"], raw["title"], intake, modules, questions)
    _validate_definition(qn)
    return qn


def _validate_definition(qn: Questionnaire) -> None:
    if DEFAULT_LOCALE not in qn.locales:
        raise ValueError(f"locales must include {DEFAULT_LOCALE}")

    def need_all(texts, where: str) -> None:
        missing = [lc for lc in qn.locales if not (isinstance(texts, dict) and str(texts.get(lc, "")).strip())]
        if missing:
            raise ValueError(f"{where}: missing translations {missing}")

    need_all(qn.title_i18n, "title")
    need_all(qn.intake["title_i18n"], "intake.title")
    for m in qn.modules:
        need_all(m["title_i18n"], f"{m['id']}.title")
    for qid, q in qn.questions.items():
        need_all(q["text_i18n"], qid)
        for o in q.get("options", []):
            need_all(q.get("option_labels", {}).get(o), f"{qid} option {o}")
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
