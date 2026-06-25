"""
cv_parser.py
-------------
Extracts raw text from an uploaded PDF resume and pulls out structured
signals: contact info, detected skills (grouped by category), and a rough
estimate of years of experience. All done locally — no external API calls.
"""

import re
import fitz  # PyMuPDF
from app.skills_db import ALL_SKILLS


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Open the PDF straight from memory and concatenate text from every page."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_email(text: str) -> str | None:
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = re.search(r"(\+?\d{1,3}[\s-]?)?\(?\d{3,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}", text)
    return match.group(0).strip() if match else None


def extract_skills(text: str) -> dict[str, list[str]]:
    """
    Scan the CV text for every known skill keyword.
    Returns skills grouped by category, e.g. {"Data Science & ML": ["python", "pandas"]}
    """
    text_lower = text.lower()
    found: dict[str, list[str]] = {}

    for skill, category in ALL_SKILLS.items():
        # word-boundary-ish match so "r" doesn't match inside "your"
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, text_lower):
            found.setdefault(category, []).append(skill)

    return found


def estimate_experience_years(text: str) -> int | None:
    """
    Looks for explicit patterns like '3 years of experience' or '2+ years'.
    This is a heuristic, not a guarantee — CVs are inconsistently written.
    """
    matches = re.findall(r"(\d+)\+?\s*(?:years|yrs)\s*(?:of)?\s*experience", text.lower())
    if matches:
        return max(int(m) for m in matches)
    return None


def parse_cv(file_bytes: bytes) -> dict:
    """Main entry point: PDF bytes in, structured profile dict out."""
    text = extract_text_from_pdf(file_bytes)

    if not text.strip():
        raise ValueError(
            "Could not extract any text from this PDF. "
            "It might be a scanned image — try a text-based PDF export instead."
        )

    skills_by_category = extract_skills(text)
    flat_skills = sorted({s for skills in skills_by_category.values() for s in skills})

    return {
        "email": extract_email(text),
        "phone": extract_phone(text),
        "experience_years": estimate_experience_years(text),
        "skills_by_category": skills_by_category,
        "skills_flat": flat_skills,
        "raw_text_preview": text[:1500],  # kept short; full text used internally only
        "raw_text_length": len(text),
    }
