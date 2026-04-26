from __future__ import annotations

from typing import Iterable

from models import (
    AnswerEvaluation,
    FinalSummary,
    GapItem,
    LearningPlanItem,
    QuestionItem,
    SkillAssessmentResult,
    SkillItem,
)


LEVEL_TO_SCORE = {
    "beginner": 0.35,
    "intermediate": 0.65,
    "advanced": 0.9,
}

CANONICAL_SKILL_NAMES = {
    "machine": "Machine Learning",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "fastapi": "FastAPI",
    "python": "Python",
    "sql": "SQL",
    "mlops": "MLOps",
    "nlp": "NLP",
    "llm": "LLM",
}


def canonical_skill_name(name: str) -> str:
    return CANONICAL_SKILL_NAMES.get(name.strip().lower(), name.strip())




def level_score(level: str | None) -> float:
    if not level:
        return 0.0
    return LEVEL_TO_SCORE.get(level.lower(), 0.0)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def dedupe_skills(skills: Iterable[SkillItem]) -> list[SkillItem]:
    seen: dict[str, SkillItem] = {}

    for item in skills:
        normalized_name = canonical_skill_name(item.skill)
        key = normalized_name.lower()

        if key not in seen:
            seen[key] = SkillItem(
                skill=normalized_name,
                importance=item.importance,
                expected_level=item.expected_level,
                claimed_level=item.claimed_level,
                evidence=item.evidence,
                confidence=item.confidence,
            )
            continue

        existing = seen[key]
        merged_evidence = list(dict.fromkeys(existing.evidence + item.evidence))

        seen[key] = SkillItem(
            skill=existing.skill,
            importance=existing.importance or item.importance,
            expected_level=existing.expected_level or item.expected_level,
            claimed_level=existing.claimed_level or item.claimed_level,
            evidence=merged_evidence,
            confidence=max(existing.confidence, item.confidence),
        )

    return list(seen.values())




def build_gap_analysis(
    jd_skills: list[SkillItem],
    resume_skills: list[SkillItem],
) -> list[GapItem]:
    resume_by_skill = {skill.skill.strip().lower(): skill for skill in resume_skills}
    gaps: list[GapItem] = []

    for jd_skill in jd_skills:
        resume_match = resume_by_skill.get(jd_skill.skill.strip().lower())
        resume_score = 0.0
        claimed_level = None
        evidence: list[str] = []

        if resume_match:
            base = level_score(resume_match.claimed_level)
            confidence_bonus = clamp(resume_match.confidence) * 0.2
            evidence_bonus = min(len(resume_match.evidence), 3) * 0.05
            resume_score = clamp(base + confidence_bonus + evidence_bonus)
            claimed_level = resume_match.claimed_level
            evidence = resume_match.evidence

        required_score = level_score(jd_skill.expected_level)
        gap_score = clamp(required_score - resume_score)

        gaps.append(
            GapItem(
                skill=jd_skill.skill,
                importance=jd_skill.importance or "important",
                expected_level=jd_skill.expected_level or "intermediate",
                claimed_level=claimed_level,
                evidence=evidence,
                resume_score=round(resume_score, 2),
                gap_score=round(gap_score, 2),
            )
        )

    gaps.sort(key=lambda item: (priority_rank(item.importance), -item.gap_score))
    return gaps


def priority_rank(importance: str) -> int:
    order = {"critical": 0, "important": 1, "optional": 2}
    return order.get(importance, 3)


def normalize_questions(raw_questions: list[dict], fallback_skill: str) -> list[QuestionItem]:
    questions: list[QuestionItem] = []
    for item in raw_questions:
        try:
            questions.append(QuestionItem(**item))
        except Exception:
            continue

    if questions:
        return questions

    return [
        QuestionItem(
            skill=fallback_skill,
            difficulty="intermediate",
            question_type="conceptual",
            prompt=f"Explain your practical experience with {fallback_skill}.",
            keywords=[fallback_skill.lower(), "experience", "project"],
        )
    ]


def evaluate_confidence(
    resume_score: float,
    answer_eval: AnswerEvaluation,
) -> float:
    gap = abs(resume_score - answer_eval.final_score)
    return round(clamp(1.0 - gap), 2)


def build_skill_result(
    gap_item: GapItem,
    answer_eval: AnswerEvaluation,
) -> SkillAssessmentResult:
    resume_score = gap_item.resume_score
    answer_score = clamp(answer_eval.final_score)
    confidence_score = evaluate_confidence(resume_score, answer_eval)
    if resume_score == 0 and answer_score > 0:
        final_skill_score = round(0.75 * answer_score + 0.25 * confidence_score, 2)
    elif answer_score == 0 and resume_score > 0:
        final_skill_score = round(0.75 * resume_score + 0.25 * confidence_score, 2)
    else:
        final_skill_score = round(
            0.35 * resume_score + 0.45 * answer_score + 0.20 * confidence_score,
            2,
        )


    if final_skill_score >= 0.8:
        status = "ready"
    elif final_skill_score >= 0.6:
        status = "near_ready"
    else:
        status = "gap"

    reasoning = (
        f"Resume score {resume_score:.2f}, answer score {answer_score:.2f}, "
        f"confidence {confidence_score:.2f}."
    )

    return SkillAssessmentResult(
        skill=gap_item.skill,
        resume_score=resume_score,
        answer_score=answer_score,
        confidence_score=confidence_score,
        final_skill_score=final_skill_score,
        status=status,
        reasoning=reasoning,
    )


def overall_score(skill_results: list[SkillAssessmentResult]) -> float:
    if not skill_results:
        return 0.0
    return round(sum(item.final_skill_score for item in skill_results) / len(skill_results), 2)


def default_hiring_recommendation(skill_results: list[SkillAssessmentResult]) -> str:
    if not skill_results:
        return "Not Yet Ready"

    critical_gaps = sum(1 for item in skill_results if item.status == "gap")
    score = overall_score(skill_results)

    if score >= 0.8 and critical_gaps == 0:
        return "Strong Match"
    if score >= 0.6:
        return "Promising, Needs Upskilling"
    return "Not Yet Ready"


def fallback_summary(skill_results: list[SkillAssessmentResult]) -> FinalSummary:
    strengths = [item.skill for item in skill_results if item.status == "ready"]
    concerns = [item.skill for item in skill_results if item.status != "ready"]
    recommendation = default_hiring_recommendation(skill_results)
    score = overall_score(skill_results)

    if recommendation == "Strong Match":
        recruiter_summary = "Candidate demonstrates solid alignment with the role across most assessed skills."
    elif recommendation == "Promising, Needs Upskilling":
        recruiter_summary = "Candidate shows a workable foundation but needs focused upskilling in a few areas."
    else:
        recruiter_summary = "Candidate is not yet ready for this role and would benefit from targeted learning before interview progression."

    return FinalSummary(
        recruiter_summary=recruiter_summary,
        strengths=strengths,
        concerns=concerns,
        hiring_recommendation=recommendation,
        overall_score=score,
        learning_plan=[],
    )


def parse_learning_plan(raw_items: list[dict]) -> list[LearningPlanItem]:
    output: list[LearningPlanItem] = []
    for item in raw_items:
        try:
            output.append(LearningPlanItem(**item))
        except Exception:
            continue
    return output
