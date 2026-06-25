"""
auth.py
--------
Password hashing + JWT issuing/verification, shared by both account types
(Company, Candidate). The JWT payload carries `sub` (user id), `role`
("company" or "candidate"), and `name`, so a single dependency can protect
routes for either role without two parallel auth systems.

SECRET_KEY: in a real deployment this MUST come from an environment
variable, never hardcoded. A fixed dev fallback is provided here purely so
the project runs out-of-the-box; see README for how to set it properly.
"""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SECRET_KEY = os.environ.get("INTERVIEW_APP_SECRET", "dev-only-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    # bcrypt has a hard 72-byte input limit — truncate defensively rather than erroring.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str, name: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "role": role, "name": name, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        )


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Generic dependency — returns {"id": int, "role": "company"|"candidate", "name": str}"""
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    payload = decode_token(token)
    return {"id": int(payload["sub"]), "role": payload["role"], "name": payload["name"]}


def require_role(required_role: str):
    """Dependency factory — use as Depends(require_role('company')) to lock a route to one role."""
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires a {required_role} account.",
            )
        return user
    return checker
