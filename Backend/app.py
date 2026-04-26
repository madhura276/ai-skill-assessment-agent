from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException

from llm import call_llm_json
from logic import (
    build_gap_analysis,
    build_skill_result,
    dedupe_skills,
    fallback_summary,
    normalize_questions,
    overall_score,
    parse_learning_plan,
)
from models import (
    AnalyzeRequest,
    AnswerEvaluation,
    AnswerRequest,
    ExtractSkillsResponse,
    FinalSummary,
    GapItem,
    QuestionSetResponse,
    SkillAssessmentResult,
)
from prompts import (
    evaluate_answer_prompt,
    extract_jd_skills_prompt,
    extract_resume_skills_prompt,
    final_summary_prompt,
    generate_questions_prompt,
    learning_plan_prompt,
)

app = FastAPI(title="AI Skill Assessment Agent", version="1.0.0")

SESSIONS: dict[str, dict] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    jd_system, jd_user = extract_jd_skills_prompt(payload.job_description)
    jd_raw = call_llm_json(jd_system, jd_user)
    jd_data = ExtractSkillsResponse(**jd_raw)

    resume_system, resume_user = extract_resume_skills_prompt(payload.resume)
    resume_raw = call_llm_json(resume_system, resume_user)
    resume_data = ExtractSkillsResponse(**resume_raw)

    jd_skills = dedupe_skills(jd_data.skills)
    resume_skills = dedupe_skills(resume_data.skills)
    gap_items = build_gap_analysis(jd_skills, resume_skills)

    if not gap_items:
        raise HTTPException(status_code=400, detail="No skills could be extracted from the job description.")

    assessment_queue: list[dict] = []

    for gap in gap_items:
        ask_count = 0

        if gap.importance == "critical":
            ask_count = 2 if gap.gap_score >= 0.3 else 1
        elif gap.importance == "important":
            ask_count = 1
        else:
            ask_count = 1 if gap.gap_score >= 0.45 else 0

        if ask_count == 0:
            continue

        q_system, q_user = generate_questions_prompt(
            skill=gap.skill,
            expected_level=gap.expected_level,
            candidate_level=gap.claimed_level,
            gap_score=gap.gap_score,
        )
        q_raw = call_llm_json(q_system, q_user)
        q_data = QuestionSetResponse(**q_raw)
        questions = normalize_questions([q.model_dump() for q in q_data.questions], gap.skill)

        for question in questions[:ask_count]:
            assessment_queue.append(
                {
                    "skill": gap.skill,
                    "expected_level": gap.expected_level,
                    "question": question.model_dump(),
                }
            )

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "job_description": payload.job_description,
        "resume": payload.resume,
        "jd_skills": [item.model_dump() for item in jd_skills],
        "resume_skills": [item.model_dump() for item in resume_skills],
        "gap_items": [item.model_dump() for item in gap_items],
        "assessment_queue": assessment_queue,
        "answers": [],
        "skill_results": {},
        "current_index": 0,
    }

    next_question = assessment_queue[0] if assessment_queue else None

    return {
        "session_id": session_id,
        "required_skills": [item.model_dump() for item in jd_skills],
        "candidate_skills": [item.model_dump() for item in resume_skills],
        "gap_analysis": [item.model_dump() for item in gap_items],
        "total_questions": len(assessment_queue),
        "next_question": next_question,
    }


@app.get("/assessment/{session_id}")
def get_assessment(session_id: str) -> dict:
    session = get_session(session_id)
    idx = session["current_index"]
    queue = session["assessment_queue"]
    next_question = queue[idx] if idx < len(queue) else None

    return {
        "session_id": session_id,
        "current_index": idx,
        "total_questions": len(queue),
        "answers": session["answers"],
        "next_question": next_question,
    }


@app.post("/assessment/{session_id}/answer")
def answer_question(session_id: str, payload: AnswerRequest) -> dict:
    session = get_session(session_id)
    idx = session["current_index"]
    queue = session["assessment_queue"]

    if idx >= len(queue):
        return build_final_summary(session_id)

    current = queue[idx]

    if not payload.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    if payload.skill.strip().lower() != current["skill"].strip().lower():
        raise HTTPException(status_code=400, detail="Answer skill does not match the current question.")

    if payload.question.strip() != current["question"]["prompt"].strip():
        raise HTTPException(status_code=400, detail="Question mismatch. Please answer the current question shown in the UI.")

    eval_system, eval_user = evaluate_answer_prompt(
        skill=payload.skill,
        question=payload.question,
        answer=payload.answer,
        expected_level=payload.expected_level,
    )
    eval_raw = call_llm_json(eval_system, eval_user)
    answer_eval = AnswerEvaluation(**eval_raw)

    gap_item = next(
        GapItem(**item)
        for item in session["gap_items"]
        if item["skill"].strip().lower() == payload.skill.strip().lower()
    )

    skill_result = build_skill_result(gap_item, answer_eval)

    session["skill_results"][payload.skill] = skill_result.model_dump()
    session["answers"].append(
        {
            "skill": payload.skill,
            "question": payload.question,
            "answer": payload.answer,
            "evaluation": answer_eval.model_dump(),
        }
    )
    session["current_index"] += 1

    if session["current_index"] >= len(queue):
        return build_final_summary(session_id)

    return {
        "complete": False,
        "evaluation": answer_eval.model_dump(),
        "skill_result": skill_result.model_dump(),
        "next_question": queue[session["current_index"]],
        "progress": {
            "answered": session["current_index"],
            "total": len(queue),
        },
    }


@app.get("/assessment/{session_id}/summary")
def get_summary(session_id: str) -> dict:
    return build_final_summary(session_id)


def build_final_summary(session_id: str) -> dict:
    session = get_session(session_id)

    skill_results = [
        SkillAssessmentResult(**item)
        for item in session["skill_results"].values()
    ]

    assessed_skills = {item.skill.lower() for item in skill_results}

    for gap in session["gap_items"]:
        gap_item = GapItem(**gap)
        if gap_item.skill.lower() in assessed_skills:
            continue

        fallback_score = round(0.75 * gap_item.resume_score + 0.10, 2)

        if fallback_score >= 0.8:
            fallback_status = "ready"
        elif fallback_score >= 0.6:
            fallback_status = "near_ready"
        else:
            fallback_status = "gap"


        skill_results.append(
            SkillAssessmentResult(
                skill=gap_item.skill,
                resume_score=gap_item.resume_score,
                answer_score=0.0,
                confidence_score=0.5,
                final_skill_score=fallback_score,
                status=fallback_status,
                reasoning="No direct answer captured for this skill, so resume evidence was used as fallback.",
            )
        )

    summary = build_llm_summary(skill_results)
    summary.learning_plan = build_llm_learning_plan(session, skill_results)
    summary.overall_score = overall_score(skill_results)

    return {
        "complete": True,
        "skill_results": [item.model_dump() for item in skill_results],
        "final_summary": summary.model_dump(),
    }


def build_llm_summary(skill_results: list[SkillAssessmentResult]) -> FinalSummary:
    try:
        system, user = final_summary_prompt([item.model_dump() for item in skill_results])
        raw = call_llm_json(system, user)
        return FinalSummary(
            recruiter_summary=raw["recruiter_summary"],
            strengths=raw.get("strengths", []),
            concerns=raw.get("concerns", []),
            hiring_recommendation=raw["hiring_recommendation"],
            overall_score=overall_score(skill_results),
            learning_plan=[],
        )
    except Exception:
        fallback = fallback_summary(skill_results)
        fallback.overall_score = overall_score(skill_results)
        return fallback


def build_llm_learning_plan(session: dict, skill_results: list[SkillAssessmentResult]):
    gap_skills = [
        {
            **result.model_dump(),
            "resume_evidence": next(
                (
                    item["evidence"]
                    for item in session["gap_items"]
                    if item["skill"].strip().lower() == result.skill.strip().lower()
                ),
                [],
            ),
        }
        for result in skill_results
        if result.status != "ready"
    ]

    if not gap_skills:
        return []

    candidate_background = {
        "resume_skills": session["resume_skills"],
        "job_description": session["job_description"],
    }

    try:
        system, user = learning_plan_prompt(gap_skills, candidate_background)
        raw = call_llm_json(system, user)
        return parse_learning_plan(raw.get("learning_plan", []))
    except Exception:
        return []


def get_session(session_id: str) -> dict:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session
