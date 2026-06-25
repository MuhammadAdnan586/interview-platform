"""
routers/cv_routes.py
----------------------
Candidate-only: upload a CV and get back the extracted profile (skills,
contact info). This is a standalone step before starting an interview —
kept separate so the frontend can show "here's what we found" before
committing to a full interview session.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.cv_parser import parse_cv
from app.auth import require_role

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/analyze")
async def analyze_cv(file: UploadFile = File(...), user: dict = Depends(require_role("candidate"))):
    if file.content_type != "application/pdf":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please upload a PDF file.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty.")

    try:
        profile = parse_cv(file_bytes)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    return {
        "email": profile["email"],
        "phone": profile["phone"],
        "experience_years": profile["experience_years"],
        "skills_by_category": profile["skills_by_category"],
        "skills_flat": profile["skills_flat"],
    }
