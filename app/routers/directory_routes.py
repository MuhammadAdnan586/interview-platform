"""
routers/directory_routes.py
------------------------------
Tiny public endpoint so the candidate dashboard can show a dropdown of
companies to interview for. No auth required — just id/name, nothing
sensitive.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company

router = APIRouter(prefix="/api/companies", tags=["directory"])


@router.get("")
def list_companies(db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.name).all()
    return [{"id": c.id, "name": c.name} for c in companies]
