# AI Interview Readiness Platform

**A multi-tenant SaaS platform that analyzes a candidate's CV, runs a personalized
mock interview (voice or typed), and produces an explainable, multi-dimensional
readiness report — not a hire/reject verdict.**

This is the **complete project — all 5 phases**, built incrementally and tested
end-to-end. Every "smart" feature (better question generation, real voice
transcription, semantic scoring, body language) is **optional and auto-detected**:
the app is fully functional with zero extra setup, and gets smarter as you
install more.

---

## What's included

| Phase | What it does |
|---|---|
| 1 | CV upload → skill/contact extraction → personalized question generation |
| 2 | Company + candidate accounts, custom questions, configurable rounds |
| 3 | Voice recording → speech-to-text → relevance, clarity & confidence scoring |
| 4 | Optional webcam clip → posture/eye-contact feedback (never a pass/fail score) |
| 5 | PDF readiness report + company-side candidate comparison dashboard |

---

## Quick start (core features, ~2 minutes)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://localhost:8000**. That's it — signup as a candidate or a company
and try the full flow. Speech-to-text and body language will show as
"not set up" until you complete the optional steps below; everything else
(typed answers, scoring, custom questions, the PDF report) works immediately.

> ⚠️ If you're on a very new Python version (3.13+) and `pymupdf` fails to
> install with a long build error, switch your virtual environment to
> Python 3.11: `py -3.11 -m venv venv`. This is a known compatibility lag
> between brand-new Python releases and some packages — not a bug in this project.

---

## Optional setup (recommended, in order of impact)

### 1. Better question generation — Ollama (free local LLM)
```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
```
Without this, questions come from a curated template bank instead of an LLM —
still relevant, just less varied.

### 2. Real voice transcription + voice tone — ~5 min, first run downloads a small model
```bash
pip install -r requirements-optional.txt
```
This installs `faster-whisper` (speech-to-text) and `librosa` (pitch/pause
analysis for the confidence score). The first time you submit a recorded
answer, it downloads a small Whisper model (~75MB) — one-time, needs internet.
Without this, candidates can still answer by typing, and typed answers are
scored normally (just without a voice-confidence score).

### 3. Stronger semantic answer scoring
Also included in `requirements-optional.txt` (`sentence-transformers`).
Without it, relevance scoring automatically falls back to a TF-IDF +
keyword-overlap heuristic — noticeably less accurate at recognizing a
good answer that doesn't reuse the question's exact wording, but it never
breaks or blocks anything.

### 4. Body language analysis (Phase 4) — fully optional
```bash
pip install mediapipe opencv-python
```
Then download two small model files into a `models/` folder in the project root:
- `models/pose_landmarker_lite.task` —
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
- `models/face_landmarker.task` —
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task

Without these, the webcam step in the interview flow can still be skipped —
or attempted, and it'll just report "not assessed" instead of analyzing anything.

**Why body language only gives descriptive signals, never a score that
blocks anything:** eye contact / posture / hand movement are coachable habits,
not reliable predictors of competence — and scoring appearance-adjacent
signals risks penalizing things unrelated to job ability (camera quality,
lighting, cultural norms around eye contact, disabilities affecting posture).
This module deliberately stays supportive-feedback-only.

---

## Project structure

```
interview-platform/
├── app/
│   ├── main.py                  # FastAPI app, wires everything together
│   ├── database.py              # SQLite via SQLAlchemy
│   ├── models.py                # DB schema (Company, Candidate, Attempt, ...)
│   ├── schemas.py                # Pydantic request/response models
│   ├── auth.py                   # JWT + password hashing
│   ├── skills_db.py               # Curated skill keyword database (Phase 1)
│   ├── cv_parser.py                # PDF text extraction + skill detection (Phase 1)
│   ├── question_gen.py             # Intro/technical/custom/awareness question builder
│   ├── scoring.py                   # Relevance + clarity scoring, score aggregation
│   ├── voice_analysis.py             # Speech-to-text + voice confidence (Phase 3)
│   ├── body_language.py               # Optional webcam analysis (Phase 4)
│   ├── report.py                       # PDF report generation (Phase 5)
│   ├── routers/
│   │   ├── auth_routes.py               # Signup/login
│   │   ├── cv_routes.py                  # CV upload/analyze
│   │   ├── interview_routes.py            # Start/answer/complete interview
│   │   ├── admin_routes.py                 # Company: questions, settings, candidates
│   │   ├── report_routes.py                 # PDF download
│   │   └── directory_routes.py               # Public company list
│   └── static/                                 # Frontend (plain HTML/CSS/JS, no build step)
│       ├── index.html, login.html, candidate_dashboard.html,
│       │   interview.html, report.html, admin_dashboard.html
│       ├── css/styles.css
│       └── js/api.js
├── models/                       # Phase 4 model files go here (not included)
├── requirements.txt              # Core dependencies
├── requirements-optional.txt     # Voice/semantic/body-language add-ons
└── interview_platform.db         # Created automatically on first run (SQLite)
```

---

## How scoring works

Each answer gets up to three sub-scores:
- **Relevance** (0–100): does the answer address the question's topic?
- **Clarity** (0–100): filler-word density, repeated words, answer length
- **Confidence** (0–100, only if voice was used): pitch variation, pause ratio

These roll up into a category breakdown (Technical, Communication, Confidence,
Body Language, Custom Questions, Awareness), each company-configurable in
weight. **A category with no data is excluded and the remaining weights are
renormalized** — nobody is penalized just because an optional module isn't
installed.

The final number is always labeled **"Overall Readiness"**, never
"Eligible/Not Eligible" — every report explicitly states it's a signal for a
human reviewer, not an automated decision.

---

## API reference

Full interactive docs (Swagger UI) at **http://localhost:8000/docs** once running.
Key endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup/company`, `/signup/candidate`, `/login` | Auth |
| POST | `/api/cv/analyze` | Upload CV, get skills/contact info |
| POST | `/api/interview/start` | Begin an attempt, get the question set |
| POST | `/api/interview/{id}/answer` | Submit one answer (audio or typed) |
| POST | `/api/interview/{id}/body-language` | Optional webcam clip |
| POST | `/api/interview/{id}/complete` | Finalize and score |
| GET | `/api/interview/{id}` | Fetch attempt detail |
| GET | `/api/interview` | List my past attempts (candidate) |
| GET/POST/DELETE | `/api/admin/questions` | Company custom questions |
| PATCH | `/api/admin/settings/rounds`, `/settings/weights` | Company configuration |
| GET | `/api/admin/candidates` | Company's candidate comparison table |
| GET | `/api/report/{id}/pdf` | Download the PDF readiness report |
| GET | `/api/companies` | Public list of companies (for the candidate dropdown) |

---

## Known limitations (be upfront about these — they're good interview talking points too)

- Skill detection is keyword-based, not true NLP entity recognition — extending
  `skills_db.py` is the easiest way to widen coverage.
- The TF-IDF/keyword-overlap fallback for relevance scoring is a heuristic; it
  under-scores answers that are correct but don't reuse the question's vocabulary.
  `sentence-transformers` fixes this — see Optional Setup #3.
- SQLite is intentionally used over Postgres/MySQL for zero-setup portability;
  for production multi-server deployment, swap `DATABASE_URL` in `database.py`.
- Body language analysis requires a one-time model download and is CPU-only —
  expect a few seconds of processing per clip, not real-time.

---

