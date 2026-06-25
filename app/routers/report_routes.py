"""
routers/report_routes.py
---------------------------
Generates and serves the PDF readiness report for a completed attempt.
The PDF is built on-demand into a temp file and streamed back — nothing
extra is stored on disk after the response is sent.
"""

import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt
from app.auth import get_current_user
from app.report import generate_report_pdf

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/{attempt_id}/pdf")
def download_report(attempt_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found.")

    # Either the candidate who took it, or the company it was taken for, can download it
    if user["role"] == "candidate" and attempt.candidate_id != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your interview attempt.")
    if user["role"] == "company" and attempt.company_id != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not one of your candidates.")

    if attempt.status != "completed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Interview isn't completed yet.")

    report_data = {
        "candidate_name": attempt.candidate.name,
        "company_name": attempt.company.name if attempt.company else None,
        "overall_score": attempt.overall_score,
        "score_breakdown": {k: v for k, v in (attempt.score_breakdown or {}).items()},
        "answers": attempt.answers or [],
        "created_at": attempt.created_at.strftime("%Y-%m-%d %H:%M") if attempt.created_at else "",
    }

    tmp_path = os.path.join(tempfile.gettempdir(), f"readiness_report_{attempt_id}.pdf")
    generate_report_pdf(report_data, tmp_path)

    filename = f"Interview_Readiness_Report_{attempt.candidate.name.replace(' ', '_')}.pdf"
    return FileResponse(tmp_path, media_type="application/pdf", filename=filename)
