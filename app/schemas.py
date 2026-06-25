"""
schemas.py
-----------
Pydantic models used for request validation and response shaping.
Keeping these separate from the SQLAlchemy models (models.py) is
deliberate — it lets the API expose a clean, stable shape even if the
underlying DB schema changes later.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, Any


# ---------- Auth ----------

class CompanySignup(BaseModel):
    name: str
    email: EmailStr
    password: str


class CandidateSignup(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


# ---------- Custom questions / admin ----------

class CustomQuestionCreate(BaseModel):
    question_text: str


class RoundSettingsUpdate(BaseModel):
    intro_enabled: Optional[bool] = None
    technical_enabled: Optional[bool] = None
    custom_enabled: Optional[bool] = None
    awareness_enabled: Optional[bool] = None


class WeightSettingsUpdate(BaseModel):
    weight_technical: Optional[float] = None
    weight_communication: Optional[float] = None
    weight_confidence: Optional[float] = None
    weight_body_language: Optional[float] = None
    weight_custom: Optional[float] = None
    weight_awareness: Optional[float] = None


# ---------- Interview flow ----------

class StartInterviewRequest(BaseModel):
    company_id: Optional[int] = None  # candidate can take a "generic" practice interview if None
    cv_profile: dict = {}


class SubmitAnswerRequest(BaseModel):
    attempt_id: int
    question_index: int
    transcript: Optional[str] = None  # used when no audio is provided (typed answer fallback)
