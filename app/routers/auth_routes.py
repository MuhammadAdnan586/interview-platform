"""
routers/auth_routes.py
------------------------
Signup + login for both account types. Two separate signup endpoints
(companies vs candidates) because they collect different fields, but a
single /login endpoint that checks both tables — the frontend doesn't
need to know which table a user lives in, it just sends email+password.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, Candidate
from app.schemas import CompanySignup, CandidateSignup, LoginRequest, TokenResponse
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup/company", response_model=TokenResponse)
def signup_company(payload: CompanySignup, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(Company.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An account with this email already exists.")

    company = Company(
        name=payload.name, email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    token = create_access_token(company.id, "company", company.name)
    return TokenResponse(access_token=token, role="company", name=company.name)


@router.post("/signup/candidate", response_model=TokenResponse)
def signup_candidate(payload: CandidateSignup, db: Session = Depends(get_db)):
    existing = db.query(Candidate).filter(Candidate.email == payload.email).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An account with this email already exists.")

    candidate = Candidate(
        name=payload.name, email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    token = create_access_token(candidate.id, "candidate", candidate.name)
    return TokenResponse(access_token=token, role="candidate", name=candidate.name)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.email == payload.email).first()
    if company and verify_password(payload.password, company.password_hash):
        token = create_access_token(company.id, "company", company.name)
        return TokenResponse(access_token=token, role="company", name=company.name)

    candidate = db.query(Candidate).filter(Candidate.email == payload.email).first()
    if candidate and verify_password(payload.password, candidate.password_hash):
        token = create_access_token(candidate.id, "candidate", candidate.name)
        return TokenResponse(access_token=token, role="candidate", name=candidate.name)

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
