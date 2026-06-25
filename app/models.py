"""
models.py
----------
Database schema. Two account types share the same login flow conceptually
but are stored in separate tables since they have different fields and
permissions:
  - Company: an employer account. Can create custom questions and view
    candidate attempts.
  - Candidate: a job-seeker account. Uploads a CV and takes interviews.

Attempt stores one full interview session: the question set used, every
answer + sub-scores, and the final aggregated breakdown — all as JSON
columns. This keeps the schema simple while still being a real relational
database (not a flat file), which is the right trade-off at this project's
scale.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Round toggles — which question rounds this company wants included
    intro_enabled = Column(Boolean, default=True)
    technical_enabled = Column(Boolean, default=True)
    custom_enabled = Column(Boolean, default=True)
    awareness_enabled = Column(Boolean, default=False)

    # Scoring weights (must sum to ~100, enforced lightly in admin_routes)
    weight_technical = Column(Float, default=30.0)
    weight_communication = Column(Float, default=20.0)
    weight_confidence = Column(Float, default=15.0)
    weight_body_language = Column(Float, default=10.0)
    weight_custom = Column(Float, default=15.0)
    weight_awareness = Column(Float, default=10.0)

    custom_questions = relationship("CustomQuestion", back_populates="company", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="company")


class CustomQuestion(Base):
    __tablename__ = "custom_questions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="custom_questions")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    attempts = relationship("Attempt", back_populates="candidate")


class Attempt(Base):
    """One full interview session for one candidate (optionally tied to a company)."""
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    cv_profile = Column(JSON, default=dict)          # extracted skills/contact info
    question_set = Column(JSON, default=list)        # the questions asked, with type/source
    answers = Column(JSON, default=list)              # list of {question, transcript, scores...}

    overall_score = Column(Float, nullable=True)
    score_breakdown = Column(JSON, default=dict)      # {"technical": 78, "communication": 65, ...}
    generation_mode = Column(String, default="template")

    status = Column(String, default="in_progress")    # in_progress | completed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    candidate = relationship("Candidate", back_populates="attempts")
    company = relationship("Company", back_populates="attempts")
