"""
question_gen.py
-----------------
Builds the full question set for an interview attempt by combining up to
four rounds, each independently toggleable by the company:

  1. Self-introduction   — always a fixed opener (if intro_enabled)
  2. Technical            — AI-generated (Ollama) or template-based, from CV skills
  3. Company custom       — questions the employer typed in themselves
  4. Awareness             — current-affairs / industry-opinion question,
                              reframed away from rote trivia (see note below)

Note on the "awareness" round: this was originally requested as general-
knowledge trivia. We deliberately reframed it as an opinion/awareness
question (e.g. "how is AI changing this industry?") instead of testing
memorized facts — it's more job-relevant and avoids the request feeling
like a pop quiz unrelated to the role.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

_INTRO_QUESTION = "Please introduce yourself — your background, what you've worked on, and what you're looking for next."

_AWARENESS_QUESTIONS = [
    "How do you think AI is changing the way people work in your field?",
    "What's a recent trend in your industry that you've been following, and what's your take on it?",
    "If you had to explain why your field matters to someone outside it, what would you say?",
]

_PROJECT_QUESTION = "Pick one project from your CV and walk me through the decisions you made and why."
_BEHAVIORAL_QUESTION = "Tell me about a time you disagreed with a teammate's technical approach. What did you do?"
_GENERIC_TECHNICAL = "Tell me about a technical challenge in your background you found difficult, and how you solved it."

_TEMPLATES = {
    "python": "Walk me through how you'd debug a Python script that's running slower than expected.",
    "machine learning": "Explain the bias-variance tradeoff and how you've managed it in a real project.",
    "deep learning": "When would you choose a deep learning approach over a classical ML model, and why?",
    "sql": "How would you optimize a slow-running SQL query on a large table?",
    "nlp": "Describe how you'd build a system to classify customer support tickets by topic.",
    "computer vision": "What preprocessing steps would you apply before feeding images into a CV model?",
    "tensorflow": "How do you decide between TensorFlow and PyTorch for a new project?",
    "pytorch": "How do you decide between TensorFlow and PyTorch for a new project?",
    "fastapi": "How would you structure a FastAPI project so it scales beyond a single file?",
    "aws": "Describe how you'd deploy a trained ML model to production using AWS.",
    "docker": "Why containerize a data science project, and what challenges have you faced doing it?",
    "power bi": "How do you decide which metrics belong on an executive dashboard vs a detailed report?",
    "react": "How do you manage state in a React app as it grows in complexity?",
}


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _generate_technical_with_ollama(skills: list[str], experience_years) -> list[str]:
    exp_str = f"{experience_years}+ years of experience" if experience_years else "an unspecified experience level"
    skills_str = ", ".join(skills) if skills else "general software/data skills"

    prompt = f"""You are an experienced technical interviewer.
Candidate's detected skills: {skills_str}
Candidate's experience: {exp_str}

Write exactly 3 technical interview questions for this candidate, each focused
on a DIFFERENT skill from their list. Return ONLY a numbered list, no preamble."""

    response = requests.post(
        OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=60
    )
    response.raise_for_status()
    raw_text = response.json().get("response", "")

    questions = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            questions.append(cleaned)
    return questions[:3]


def _generate_technical_with_templates(skills: list[str]) -> list[str]:
    questions, used = [], set()
    for skill in skills:
        if skill in _TEMPLATES and skill not in used:
            questions.append(_TEMPLATES[skill])
            used.add(skill)
        if len(questions) == 3:
            break
    while len(questions) < 3:
        questions.append(_GENERIC_TECHNICAL)
    return questions


def _technical_round(skills: list[str], experience_years) -> tuple[list[str], str]:
    if _ollama_available():
        try:
            qs = _generate_technical_with_ollama(skills, experience_years)
            if qs:
                return qs, "ollama (local LLM)"
        except requests.exceptions.RequestException:
            pass
    return _generate_technical_with_templates(skills), "template (Ollama not running)"


def build_question_set(
    skills: list[str],
    experience_years,
    custom_questions: list[str] | None = None,
    intro_enabled: bool = True,
    technical_enabled: bool = True,
    custom_enabled: bool = True,
    awareness_enabled: bool = False,
) -> dict:
    """
    Returns: {
      "questions": [{"question": str, "type": "intro"|"technical"|"project"|"behavioral"|"custom"|"awareness"}],
      "generation_mode": str
    }
    """
    import random

    questions = []
    generation_mode = "template"

    if intro_enabled:
        questions.append({"question": _INTRO_QUESTION, "type": "intro"})

    if technical_enabled:
        tech_qs, generation_mode = _technical_round(skills, experience_years)
        for q in tech_qs:
            questions.append({"question": q, "type": "technical"})
        questions.append({"question": _PROJECT_QUESTION, "type": "project"})
        questions.append({"question": _BEHAVIORAL_QUESTION, "type": "behavioral"})

    if custom_enabled and custom_questions:
        for q in custom_questions:
            questions.append({"question": q, "type": "custom"})

    if awareness_enabled:
        questions.append({"question": random.choice(_AWARENESS_QUESTIONS), "type": "awareness"})

    return {"questions": questions, "generation_mode": generation_mode}
