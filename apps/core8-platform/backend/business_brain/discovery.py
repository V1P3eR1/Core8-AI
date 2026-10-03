"""Discovery flow: validate answers, persist them, and project them into Brain facts."""

from business_brain.questionnaire import (
    AnswerError, Questionnaire, applicable_questions, validate_answer,
)
from business_brain.repository import BrainRepository, stricter

SOURCE_QUESTIONNAIRE = "questionnaire"


class AssessmentClosed(Exception):
    pass


def fact_key_for(question_id: str) -> str:
    return f"q:{question_id}"


def _module_sensitivity(qn: Questionnaire, module_id: str, answers: dict) -> str | None:
    if module_id == qn.intake["id"]:
        return None
    return answers.get(f"{module_id}.data_sensitivity")


def _fact_sensitivity(qn: Questionnaire, q: dict, answers: dict) -> str:
    level = q.get("sensitivity", "internal")
    module_level = _module_sensitivity(qn, q["module"], answers)
    return stricter(level, module_level) if module_level else level


async def submit_answers(
    repo: BrainRepository, qn: Questionnaire, assessment: dict, incoming: dict, user_id: str,
) -> dict:
    """Validate and store a batch of answers; update the Brain. Returns {changed_facts, retracted}.

    Raises AnswerError (client error) or AssessmentClosed.
    """
    if assessment["status"] != "in_progress":
        raise AssessmentClosed()
    if assessment["questionnaire_version"] != qn.version:
        raise AnswerError("assessment uses a different questionnaire version")
    if not isinstance(incoming, dict) or not incoming:
        raise AnswerError("answers must be a non-empty object")

    unknown = [qid for qid in incoming if qid not in qn.questions]
    if unknown:
        raise AnswerError(f"unknown questions: {unknown}")

    cleaned = {qid: validate_answer(qn.questions[qid], v) for qid, v in incoming.items()}
    previous = await repo.get_answers(assessment["id"])
    merged = {**previous, **cleaned}

    applicable_ids = {q["id"] for q in applicable_questions(qn, merged)}
    not_applicable = [qid for qid in cleaned if qid not in applicable_ids]
    if not_applicable:
        raise AnswerError(f"questions not active for this assessment: {not_applicable}")

    await repo.save_answers(assessment["id"], cleaned, user_id)

    # Tighten module sensitivity first, so facts below are written at the right level.
    for qid, value in cleaned.items():
        q = qn.questions[qid]
        if q.get("field") == "data_sensitivity":
            await repo.tighten_domain_sensitivity(q["domain"], value)

    # Project answers into facts: this batch's answers, plus earlier answers whose fact is not
    # active (a module was re-activated). Earlier answers with an active fact are left alone so an
    # accepted correction is never silently reverted.
    changed = 0
    for qid, value in merged.items():
        if qid not in applicable_ids:
            continue
        if qid not in cleaned and await repo.has_active_fact(fact_key_for(qid)):
            continue
        q = qn.questions[qid]
        _, did_change = await repo.upsert_fact(
            fact_key=fact_key_for(qid),
            category=q["maps_to"]["category"],
            domain=q["domain"],
            value={"question": q["text"], "answer": value, "field": q["maps_to"].get("key") or q.get("field")},
            sensitivity=_fact_sensitivity(qn, q, merged),
            source_type=SOURCE_QUESTIONNAIRE,
            source_ref=f"assessment:{assessment['id']}#{qid}",
            created_by=user_id,
        )
        changed += int(did_change)

    # Answers to modules that are no longer active must not keep feeding agents.
    retracted = 0
    for qid in previous:
        if qid not in applicable_ids:
            await repo.retract_fact(fact_key_for(qid))
            retracted += 1

    return {"changed_facts": changed, "retracted_facts": retracted}
