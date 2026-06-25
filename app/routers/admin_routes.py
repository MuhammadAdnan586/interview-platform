"""
routers/admin_routes.py
--------------------------
Company-only routes (protected by require_role("company")):
  - CRUD on custom interview questions
  - Toggle which rounds are active (intro/technical/custom/awareness)
  - Adjust scoring weights
  - View all candidate attempts for this company, sorted by score
    (the "comparison dashboard")
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, CustomQuestion, Attempt
from app.schemas import CustomQuestionCreate, RoundSettingsUpdate, WeightSettingsUpdate
from app.auth import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_company(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found.")
    return company


# ---------- Custom questions ----------

@router.get("/questions")
def list_questions(user: dict = Depends(require_role("company")), db: Session = Depends(get_db)):
    questions = db.query(CustomQuestion).filter(CustomQuestion.company_id == user["id"]).all()
    return [{"id": q.id, "question_text": q.question_text} for q in questions]


@router.post("/questions")
def add_question(payload: CustomQuestionCreate, user: dict = Depends(require_role("company")),
                  db: Session = Depends(get_db)):
    q = CustomQuestion(company_id=user["id"], question_text=payload.question_text)
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"id": q.id, "question_text": q.question_text}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, user: dict = Depends(require_role("company")),
                     db: Session = Depends(get_db)):
    q = db.query(CustomQuestion).filter(
        CustomQuestion.id == question_id, CustomQuestion.company_id == user["id"]
    ).first()
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found.")
    db.delete(q)
    db.commit()
    return {"deleted": True}


# ---------- Round + weight settings ----------

@router.get("/settings")
def get_settings(user: dict = Depends(require_role("company")), db: Session = Depends(get_db)):
    company = _get_company(db, user["id"])
    return {
        "rounds": {
            "intro_enabled": company.intro_enabled,
            "technical_enabled": company.technical_enabled,
            "custom_enabled": company.custom_enabled,
            "awareness_enabled": company.awareness_enabled,
        },
        "weights": {
            "technical": company.weight_technical,
            "communication": company.weight_communication,
            "confidence": company.weight_confidence,
            "body_language": company.weight_body_language,
            "custom": company.weight_custom,
            "awareness": company.weight_awareness,
        },
    }


@router.patch("/settings/rounds")
def update_rounds(payload: RoundSettingsUpdate, user: dict = Depends(require_role("company")),
                   db: Session = Depends(get_db)):
    company = _get_company(db, user["id"])
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    return {"updated": True}


@router.patch("/settings/weights")
def update_weights(payload: WeightSettingsUpdate, user: dict = Depends(require_role("company")),
                    db: Session = Depends(get_db)):
    company = _get_company(db, user["id"])
    field_map = {
        "weight_technical": payload.weight_technical,
        "weight_communication": payload.weight_communication,
        "weight_confidence": payload.weight_confidence,
        "weight_body_language": payload.weight_body_language,
        "weight_custom": payload.weight_custom,
        "weight_awareness": payload.weight_awareness,
    }
    for field, value in field_map.items():
        if value is not None:
            setattr(company, field, value)
    db.commit()
    return {"updated": True}


# ---------- Candidate comparison dashboard ----------

@router.get("/candidates")
def list_candidates(user: dict = Depends(require_role("company")), db: Session = Depends(get_db)):
    attempts = (
        db.query(Attempt)
        .filter(Attempt.company_id == user["id"], Attempt.status == "completed")
        .order_by(Attempt.overall_score.desc())
        .all()
    )
    return [
        {
            "attempt_id": a.id,
            "candidate_name": a.candidate.name,
            "candidate_email": a.candidate.email,
            "overall_score": a.overall_score,
            "score_breakdown": a.score_breakdown,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attempts
    ]
