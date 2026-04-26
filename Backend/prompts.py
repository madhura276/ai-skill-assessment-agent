from __future__ import annotations

import json


JSON_ONLY_RULE = (
    "Return valid JSON only. No markdown, no explanation, no code fences."
)


def extract_jd_skills_prompt(job_description: str) -> tuple[str, str]:
    system = (
        "You extract job skills from job descriptions. "
        + JSON_ONLY_RULE
    )
    user = f"""
Extract only meaningful professional or technical skills from this job description.

Return JSON in this format:
{{
  "skills": [
    {{
      "skill": "Python",
      "importance": "critical",
      "expected_level": "advanced"
    }}
  ]
}}

Rules:
- `importance` must be one of: critical, important, optional
- `expected_level` must be one of: beginner, intermediate, advanced
- Ignore generic soft skills unless the JD clearly centers them
- Deduplicate skills

Job description:
{job_description}
""".strip()
    return system, user


def extract_resume_skills_prompt(resume_text: str) -> tuple[str, str]:
    system = (
        "You extract candidate skills and supporting evidence from resumes. "
        + JSON_ONLY_RULE
    )
    user = f"""
Extract skills from this resume.

Return JSON in this format:
{{
  "skills": [
    {{
      "skill": "Python",
      "claimed_level": "intermediate",
      "evidence": ["Built FastAPI APIs", "Used pandas for analytics"],
      "confidence": 0.78
    }}
  ]
}}

Rules:
- `claimed_level` must be one of: beginner, intermediate, advanced
- `confidence` must be between 0 and 1
- Evidence must quote short resume-backed phrases, not invented claims
- Deduplicate skills

Resume:
{resume_text}
""".strip()
    return system, user


def generate_questions_prompt(
    skill: str,
    expected_level: str,
    candidate_level: str | None,
    gap_score: float,
) -> tuple[str, str]:
    system = (
        "You generate technical assessment questions for hiring. "
        + JSON_ONLY_RULE
    )
    user = f"""
Generate 2 interview questions for this skill.

Skill: {skill}
Expected level: {expected_level}
Candidate level from resume: {candidate_level or "unknown"}
Gap score: {gap_score}

Return JSON in this format:
{{
  "questions": [
    {{
      "skill": "{skill}",
      "difficulty": "{expected_level}",
      "question_type": "conceptual",
      "prompt": "question text",
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }},
    {{
      "skill": "{skill}",
      "difficulty": "{expected_level}",
      "question_type": "practical",
      "prompt": "question text",
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}

Rules:
- Ask one conceptual and one practical question
- Match question difficulty to expected level
- If gap_score is high, start more fundamental
- Keywords should be useful for answer evaluation
""".strip()
    return system, user


def evaluate_answer_prompt(
    skill: str,
    question: str,
    answer: str,
    expected_level: str,
) -> tuple[str, str]:
    system = (
        "You evaluate technical interview answers consistently. "
        + JSON_ONLY_RULE
    )
    user = f"""
Evaluate this candidate answer.

Skill: {skill}
Expected level: {expected_level}
Question: {question}
Answer: {answer}

Return JSON in this format:
{{
  "technical_accuracy": 0.72,
  "depth": 0.68,
  "clarity": 0.81,
  "final_score": 0.74,
  "feedback": "Good fundamentals, but missing production-level detail."
}}

Rules:
- All scores must be between 0 and 1
- Be strict but fair
- Reward correctness, practical understanding, and specificity
- Penalize vague or generic answers
- Feedback must be 1 short sentence
""".strip()
    return system, user


def final_summary_prompt(skill_results: list[dict]) -> tuple[str, str]:
    system = (
        "You write concise recruiter-facing assessment summaries. "
        + JSON_ONLY_RULE
    )
    user = f"""
Using these skill assessment results, produce a final hiring summary.

Skill results:
{json.dumps(skill_results, indent=2)}

Return JSON in this format:
{{
  "recruiter_summary": "short paragraph",
  "strengths": ["item1", "item2"],
  "concerns": ["item1", "item2"],
  "hiring_recommendation": "Strong Match"
}}

Rules:
- `hiring_recommendation` must be one of:
  - Strong Match
  - Promising, Needs Upskilling
  - Not Yet Ready
- Keep the summary concrete and evidence-based
""".strip()
    return system, user


def learning_plan_prompt(
    gap_skills: list[dict],
    candidate_background: dict,
) -> tuple[str, str]:
    system = (
        "You create realistic learning plans grounded in adjacent skills. "
        + JSON_ONLY_RULE
    )
    user = f"""
Create a personalized learning plan for this candidate.

Gap skills:
{json.dumps(gap_skills, indent=2)}

Candidate background:
{json.dumps(candidate_background, indent=2)}

Return JSON in this format:
{{
  "learning_plan": [
    {{
      "skill": "MLOps",
      "why_it_matters": "short reason",
      "adjacent_skills": ["Docker", "Monitoring"],
      "resources": [
        {{"title": "Resource name", "url": "https://example.com", "type": "course"}}
      ],
      "weekly_plan": ["Week 1 ...", "Week 2 ...", "Week 3 ..."],
      "estimated_hours_per_week": 6,
      "estimated_weeks": 3
    }}
  ]
}}

Rules:
- Recommend realistic next steps, not a huge curriculum
- Use adjacent skills the candidate can plausibly learn next
- Keep plans practical and concise
""".strip()
    return system, user
