from __future__ import annotations

import os
from io import BytesIO

import pandas as pd
import requests
import streamlit as st
from docx import Document # type: ignore
from PyPDF2 import PdfReader # type: ignore

API_BASE_URL = os.getenv("API_BASE_URL") or st.secrets.get("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="AI Skill Assessment Agent", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "final_result" not in st.session_state:
    st.session_state.final_result = None
if "last_eval" not in st.session_state:
    st.session_state.last_eval = None
if "answer_box_version" not in st.session_state:
    st.session_state.answer_box_version = 0


def post_json(path: str, payload: dict) -> dict:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def get_json(path: str) -> dict:
    response = requests.get(f"{API_BASE_URL}{path}", timeout=60)
    response.raise_for_status()
    return response.json()


def format_for_table(items: list[dict]) -> pd.DataFrame:
    rows = []
    for item in items:
        row = dict(item)
        if isinstance(row.get("evidence"), list):
            row["evidence"] = ", ".join(row["evidence"])
        rows.append(row)
    return pd.DataFrame(rows)


def extract_resume_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    if file_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(uploaded_file.read()))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()

    if file_name.endswith(".docx"):
        document = Document(BytesIO(uploaded_file.read()))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()

    return ""


def reset_state() -> None:
    st.session_state.session_id = None
    st.session_state.analysis = None
    st.session_state.current_question = None
    st.session_state.final_result = None
    st.session_state.last_eval = None
    st.session_state.answer_box_version = 0


st.title("AI-Powered Skill Assessment & Personalised Learning Plan Agent")
st.caption("Analyze a JD and resume, assess real proficiency, identify gaps, and generate an upskilling plan.")

col1, col2 = st.columns(2)

with col1:
    jd_text = st.text_area(
        "Job Description",
        height=260,
        value="""We are hiring an AI Engineer with strong Python, SQL, FastAPI, Machine Learning, and MLOps experience.
The candidate should be able to build APIs, evaluate ML models, deploy services, monitor production systems, and collaborate with product teams.
Experience with NLP and LLM workflows is a plus.""",
    )

with col2:
    uploaded_resume = st.file_uploader(
        "Upload Resume",
        type=["pdf", "txt", "docx"],
        help="Upload a candidate resume in PDF, TXT, or DOCX format.",
    )

    default_resume_text = """AI Developer with hands-on experience in Python, FastAPI, and NLP-based projects.
Built internal tools using pandas and deployed small machine learning prototypes.
Familiar with SQL for reporting and analytics.
Worked on prompt engineering and text classification side projects.
Limited production experience with MLOps, monitoring, and model serving pipelines."""

    uploaded_resume_text = extract_resume_text(uploaded_resume) if uploaded_resume else ""

    resume_text = st.text_area(
        "Candidate Resume",
        height=260,
        value=uploaded_resume_text if uploaded_resume_text else default_resume_text,
    )

a, b = st.columns([1, 1])

with a:
    if st.button("Analyze Match", use_container_width=True):
        try:
            result = post_json(
                "/analyze",
                {"job_description": jd_text, "resume": resume_text},
            )
            st.session_state.session_id = result["session_id"]
            st.session_state.analysis = result
            st.session_state.current_question = result["next_question"]
            st.session_state.final_result = None
            st.session_state.last_eval = None
            st.session_state.answer_box_version = 0
            st.rerun()
        except requests.HTTPError as exc:
            try:
                st.error(exc.response.json().get("detail", exc.response.text))
            except Exception:
                st.error(exc.response.text)

with b:
    if st.button("Reset", use_container_width=True):
        reset_state()
        st.rerun()

analysis = st.session_state.analysis

if analysis:
    st.subheader("1. Extraction and Gap Analysis")

    required_df = format_for_table(analysis.get("required_skills", []))
    resume_df = format_for_table(analysis.get("candidate_skills", []))
    gap_df = format_for_table(analysis.get("gap_analysis", []))

    x, y, z = st.columns(3)

    with x:
        st.markdown("**Required Skills**")
        if required_df.empty:
            st.info("No required skills extracted yet.")
        else:
            st.dataframe(required_df, use_container_width=True, hide_index=True)

    with y:
        st.markdown("**Resume Skills**")
        if resume_df.empty:
            st.info("No resume skills extracted yet.")
        else:
            st.dataframe(resume_df, use_container_width=True, hide_index=True)

    with z:
        st.markdown("**Gap Analysis**")
        if gap_df.empty:
            st.info("No gap analysis available yet.")
        else:
            st.dataframe(gap_df, use_container_width=True, hide_index=True)

    st.info(f"Assessment queue created with {analysis.get('total_questions', 0)} questions.")

if st.session_state.current_question and not st.session_state.final_result:
    question_block = st.session_state.current_question
    question = question_block["question"]

    st.subheader("2. Conversational Assessment")
    st.write(
        f"**Skill:** {question_block['skill']} | "
        f"**Expected Level:** {question_block['expected_level']} | "
        f"**Type:** {question['question_type']}"
    )
    st.write(question["prompt"])

    total_questions = st.session_state.analysis.get("total_questions", 0) if st.session_state.analysis else 0
    answered_count = 0

    if st.session_state.session_id:
        try:
            assessment_state = get_json(f"/assessment/{st.session_state.session_id}")
            answered_count = len(assessment_state.get("answers", []))
        except Exception:
            answered_count = 0

    if total_questions > 0:
        st.progress(min((answered_count + 1) / total_questions, 1.0))
        st.caption(f"Question {answered_count + 1} of {total_questions}")

    answer_key = f"answer_text_{st.session_state.answer_box_version}"
    answer_value = st.text_area("Candidate Answer", height=180, key=answer_key)

    if st.button("Submit Answer", use_container_width=True):
        answer_value = answer_value.strip()

        if not answer_value:
            st.warning("Please enter an answer first.")
        else:
            try:
                result = post_json(
                    f"/assessment/{st.session_state.session_id}/answer",
                    {
                        "skill": question_block["skill"],
                        "question": question["prompt"],
                        "answer": answer_value,
                        "expected_level": question_block["expected_level"],
                    },
                )

                st.session_state.answer_box_version += 1

                if result.get("complete"):
                    st.session_state.final_result = result
                    st.session_state.current_question = None
                    st.session_state.last_eval = None
                else:
                    st.session_state.last_eval = result
                    st.session_state.current_question = result["next_question"]

                st.rerun()

            except requests.HTTPError as exc:
                try:
                    st.error(exc.response.json().get("detail", exc.response.text))
                except Exception:
                    st.error(exc.response.text)

if st.session_state.last_eval and not st.session_state.final_result:
    st.subheader("Previous Answer Evaluation")
    eval_data = st.session_state.last_eval["evaluation"]
    skill_result = st.session_state.last_eval["skill_result"]

    p, q = st.columns(2)

    with p:
        st.metric("Answer Score", eval_data["final_score"])
        st.metric("Technical Accuracy", eval_data["technical_accuracy"])
        st.metric("Depth", eval_data["depth"])
        st.metric("Clarity", eval_data["clarity"])

    with q:
        st.metric("Current Skill Score", skill_result["final_skill_score"])
        st.metric("Status", skill_result["status"])
        st.write(eval_data["feedback"])

if st.session_state.final_result:
    final_result = st.session_state.final_result
    summary = final_result["final_summary"]
    skill_results = final_result["skill_results"]

    st.subheader("3. Final Hiring Summary")

    a1, a2, a3 = st.columns(3)
    with a1:
        st.metric("Overall Score", summary["overall_score"])
    with a2:
        st.metric("Recommendation", summary["hiring_recommendation"])
    with a3:
        st.metric("Skills Assessed", len(skill_results))

    st.write(summary["recruiter_summary"])

    left, right = st.columns(2)

    with left:
        st.markdown("**Strengths**")
        strengths = summary.get("strengths", [])
        if strengths:
            for item in strengths:
                st.write(f"- {item}")
        else:
            st.write("No strengths listed.")

    with right:
        st.markdown("**Concerns**")
        concerns = summary.get("concerns", [])
        if concerns:
            for item in concerns:
                st.write(f"- {item}")
        else:
            st.write("No concerns listed.")

    st.markdown("**Per-Skill Results**")
    st.dataframe(pd.DataFrame(skill_results), use_container_width=True)

    st.subheader("4. Personalized Learning Plan")
    learning_plan = summary.get("learning_plan", [])

    if not learning_plan:
        st.success("No learning plan needed or no gap skills found.")
    else:
        for item in learning_plan:
            with st.container(border=True):
                st.markdown(f"### {item['skill']}")
                st.write(item["why_it_matters"])
                st.write(
                    f"Estimated effort: {item['estimated_weeks']} weeks, "
                    f"{item['estimated_hours_per_week']} hours/week"
                )
                st.write("Adjacent skills:", ", ".join(item.get("adjacent_skills", [])))

                st.markdown("**Weekly Plan**")
                for step in item.get("weekly_plan", []):
                    st.write(f"- {step}")

                st.markdown("**Resources**")
                for resource in item.get("resources", []):
                    title = resource.get("title", "Resource")
                    url = resource.get("url", "#")
                    rtype = resource.get("type", "resource")
                    st.write(f"- [{title}]({url}) ({rtype})")
