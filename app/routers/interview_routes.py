"""
routers/interview_routes.py
------------------------------
The core interview flow, candidate-only:

  POST /api/interview/start            -> creates an Attempt, returns the question set
  POST /api/interview/{id}/answer      -> submit one answer (audio file OR typed text)
  POST /api/interview/{id}/body-language -> optional: upload one short video for the session
  POST /api/interview/{id}/complete    -> finalize, compute aggregate scores
  GET  /api/interview/{id}             -> fetch attempt detail (for the report page)

Audio/video files are processed and then deleted — only the resulting
transcript/scores are persisted, not the raw recordings.
"""

import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt, Candidate, Company, CustomQuestion
from app.schemas import StartInterviewRequest
from app.auth import require_role
from app.question_gen import build_question_set
from app import voice_analysis, scoring, body_language

router = APIRouter(prefix="/api/interview", tags=["interview"])


def _get_attempt_or_404(db: Session, attempt_id: int, candidate_id: int) -> Attempt:
    attempt = db.query(Attempt).filter(
        Attempt.id == attempt_id, Attempt.candidate_id == candidate_id
    ).first()
    if not attempt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview attempt not found.")
    return attempt


@router.post("/start")
def start_interview(payload: StartInterviewRequest,
                     user: dict = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    """
    payload.cv_profile is the dict returned by /api/cv/analyze (skills_flat,
    experience_years, etc.) passed back in so we don't need to re-parse or
    store the raw CV.
    """
    cv_profile = payload.cv_profile
    intro_enabled, technical_enabled, custom_enabled, awareness_enabled = True, True, True, False
    custom_questions = []
    company = None

    if payload.company_id:
        company = db.query(Company).filter(Company.id == payload.company_id).first()
        if not company:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found.")
        intro_enabled = company.intro_enabled
        technical_enabled = company.technical_enabled
        custom_enabled = company.custom_enabled
        awareness_enabled = company.awareness_enabled
        custom_questions = [q.question_text for q in
                             db.query(CustomQuestion).filter(CustomQuestion.company_id == company.id).all()]

    question_data = build_question_set(
        skills=cv_profile.get("skills_flat", []),
        experience_years=cv_profile.get("experience_years"),
        custom_questions=custom_questions,
        intro_enabled=intro_enabled, technical_enabled=technical_enabled,
        custom_enabled=custom_enabled, awareness_enabled=awareness_enabled,
    )

    attempt = Attempt(
        candidate_id=user["id"],
        company_id=payload.company_id,
        cv_profile=cv_profile,
        question_set=question_data["questions"],
        answers=[],
        generation_mode=question_data["generation_mode"],
        status="in_progress",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "questions": question_data["questions"],
        "generation_mode": question_data["generation_mode"],
    }


@router.post("/{attempt_id}/answer")
async def submit_answer(
    attempt_id: int,
    question_index: int = Form(...),
    transcript: str | None = Form(None),
    audio: UploadFile | None = File(None),
    user: dict = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_or_404(db, attempt_id, user["id"])
    questions = attempt.question_set
    if question_index < 0 or question_index >= len(questions):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid question_index.")

    question = questions[question_index]
    confidence_score = None
    final_transcript = transcript or ""
    transcription_note = "typed"

    if audio is not None:
        suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        try:
            stt_result = voice_analysis.transcribe_audio(tmp_path)
            if stt_result["available"]:
                final_transcript = stt_result["transcript"]
                transcription_note = "speech-to-text"
            else:
                transcription_note = stt_result["message"]

            voice_result = voice_analysis.voice_confidence_score(tmp_path)
            if voice_result["available"]:
                confidence_score = voice_result["score"]
        finally:
            os.unlink(tmp_path)

    relevance, relevance_method = scoring.relevance_score(question["question"], final_transcript)
    clarity = scoring.communication_clarity_score(final_transcript)

    answer_entry = {
        "question_index": question_index,
        "question": question["question"],
        "type": question["type"],
        "transcript": final_transcript,
        "transcription_note": transcription_note,
        "relevance_score": relevance,
        "relevance_method": relevance_method,
        "clarity_score": clarity["score"],
        "confidence_score": confidence_score,
    }

    answers = list(attempt.answers or [])
    answers = [a for a in answers if a["question_index"] != question_index]  # replace if resubmitted
    answers.append(answer_entry)
    attempt.answers = answers
    db.commit()

    return answer_entry


@router.post("/{attempt_id}/body-language")
async def submit_body_language(
    attempt_id: int,
    video: UploadFile = File(...),
    user: dict = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_or_404(db, attempt_id, user["id"])

    suffix = os.path.splitext(video.filename or "clip.mp4")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await video.read())
        tmp_path = tmp.name

    try:
        result = body_language.analyze_video(tmp_path)
    finally:
        os.unlink(tmp_path)

    cv_profile = dict(attempt.cv_profile or {})
    cv_profile["_body_language"] = result
    attempt.cv_profile = cv_profile
    db.commit()

    return result


@router.post("/{attempt_id}/complete")
def complete_interview(attempt_id: int, user: dict = Depends(require_role("candidate")),
                        db: Session = Depends(get_db)):
    attempt = _get_attempt_or_404(db, attempt_id, user["id"])

    weights = None
    if attempt.company_id:
        company = db.query(Company).filter(Company.id == attempt.company_id).first()
        if company:
            weights = {
                "technical": company.weight_technical,
                "communication": company.weight_communication,
                "confidence": company.weight_confidence,
                "body_language": company.weight_body_language,
                "custom": company.weight_custom,
                "awareness": company.weight_awareness,
            }

    body_language_result = (attempt.cv_profile or {}).get("_body_language") or {}
    body_language_score = None
    if body_language_result.get("available") and body_language_result.get("posture_score") is not None:
        eye = body_language_result.get("eye_contact_pct") or 0
        posture = body_language_result.get("posture_score") or 0
        body_language_score = round((eye + posture) / 2, 1)

    result = scoring.aggregate_scores(attempt.answers or [], weights=weights, body_language_score=body_language_score)

    attempt.overall_score = result["overall_score"]
    attempt.score_breakdown = result["breakdown"]
    attempt.status = "completed"
    db.commit()

    return {
        "attempt_id": attempt.id,
        "overall_score": attempt.overall_score,
        "score_breakdown": attempt.score_breakdown,
    }


@router.get("")
def list_my_attempts(user: dict = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    attempts = (
        db.query(Attempt)
        .filter(Attempt.candidate_id == user["id"])
        .order_by(Attempt.created_at.desc())
        .all()
    )
    return [
        {
            "attempt_id": a.id,
            "status": a.status,
            "company_name": a.company.name if a.company else "Practice (no company)",
            "overall_score": a.overall_score,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attempts
    ]


@router.get("/{attempt_id}")
def get_attempt(attempt_id: int, user: dict = Depends(require_role("candidate")), db: Session = Depends(get_db)):
    attempt = _get_attempt_or_404(db, attempt_id, user["id"])
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "questions": attempt.question_set,
        "answers": attempt.answers,
        "overall_score": attempt.overall_score,
        "score_breakdown": attempt.score_breakdown,
        "generation_mode": attempt.generation_mode,
        "company_id": attempt.company_id,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }
