from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SkillImportance = Literal["critical", "important", "optional"]
SkillLevel = Literal["beginner", "intermediate", "advanced"]
SkillStatus = Literal["ready", "near_ready", "gap"]


class AnalyzeRequest(BaseModel):
    job_description: str = Field(min_length=20)
    resume: str = Field(min_length=20)


class SkillItem(BaseModel):
    skill: str
    importance: SkillImportance | None = None
    expected_level: SkillLevel | None = None
    claimed_level: SkillLevel | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ExtractSkillsResponse(BaseModel):
    skills: list[SkillItem] = Field(default_factory=list)


class GapItem(BaseModel):
    skill: str
    importance: SkillImportance
    expected_level: SkillLevel
    claimed_level: SkillLevel | None = None
    evidence: list[str] = Field(default_factory=list)
    resume_score: float = 0.0
    gap_score: float = 0.0


class QuestionItem(BaseModel):
    skill: str
    difficulty: SkillLevel
    question_type: Literal["conceptual", "practical"]
    prompt: str
    keywords: list[str] = Field(default_factory=list)


class QuestionSetResponse(BaseModel):
    questions: list[QuestionItem] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    skill: str
    question: str
    answer: str = Field(min_length=1)
    expected_level: SkillLevel


class AnswerEvaluation(BaseModel):
    technical_accuracy: float = 0.0
    depth: float = 0.0
    clarity: float = 0.0
    final_score: float = 0.0
    feedback: str = ""


class SkillAssessmentResult(BaseModel):
    skill: str
    resume_score: float = 0.0
    answer_score: float = 0.0
    confidence_score: float = 0.0
    final_skill_score: float = 0.0
    status: SkillStatus = "gap"
    reasoning: str = ""


class LearningPlanItem(BaseModel):
    skill: str
    why_it_matters: str
    adjacent_skills: list[str] = Field(default_factory=list)
    resources: list[dict] = Field(default_factory=list)
    weekly_plan: list[str] = Field(default_factory=list)
    estimated_hours_per_week: int = 0
    estimated_weeks: int = 0


class FinalSummary(BaseModel):
    recruiter_summary: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    hiring_recommendation: Literal[
        "Strong Match",
        "Promising, Needs Upskilling",
        "Not Yet Ready",
    ]
    overall_score: float = 0.0
    learning_plan: list[LearningPlanItem] = Field(default_factory=list)
