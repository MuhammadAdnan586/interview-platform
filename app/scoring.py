"""
scoring.py
-----------
Text-based scoring for a candidate's transcribed answer:

  1. Relevance score   — how well the answer matches the question's topic.
     Tries sentence-transformers (better semantic understanding) first;
     falls back to TF-IDF cosine similarity (pure scikit-learn, no model
     download required) if sentence-transformers/its model isn't available.
     This mirrors the Ollama fallback pattern from Phase 1: best available
     method is used automatically, nothing ever hard-fails.

  2. Communication clarity score — filler-word density, sentence length
     sanity, and repeated-word ratio. Deliberately rule-based rather than
     another ML model: clarity is well captured by these signals, and
     keeping it rule-based means zero extra dependencies/downloads.

All scores are 0-100.
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

_FILLER_WORDS = {
    "um", "uh", "umm", "uhh", "like", "you know", "sort of", "kind of",
    "basically", "actually", "literally", "i mean", "so yeah",
}

# A few question-phrasing words that ENGLISH_STOP_WORDS doesn't cover but
# show up constantly in interview questions without carrying topic meaning.
_EXTRA_STOPWORDS = {"would", "could", "describe", "explain", "tell", "walk", "think"}
_STOPWORDS = ENGLISH_STOP_WORDS | _EXTRA_STOPWORDS

_embedding_model = None
_embedding_model_load_attempted = False


def _try_load_embedding_model():
    """Lazy-load sentence-transformers only once; never raises."""
    global _embedding_model, _embedding_model_load_attempted
    if _embedding_model_load_attempted:
        return _embedding_model
    _embedding_model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _embedding_model = None
    return _embedding_model


def _simple_stem(word: str) -> str:
    """
    Crude suffix-stripping so 'debugging'/'debug' and 'slower'/'slow' count
    as the same word for overlap purposes. Not real morphology — just
    enough to stop obviously-related words from being treated as unrelated,
    which is the main reason the keyword-overlap fallback under-scores
    good answers.
    """
    for suffix in ("ing", "edly", "ed", "ies", "es", "er", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _content_words(text: str) -> set[str]:
    raw = re.findall(r"[a-z']+", text.lower())
    return {_simple_stem(w) for w in raw if len(w) > 2 and w not in _STOPWORDS}


def relevance_score(question: str, transcript: str) -> tuple[float, str]:
    """Returns (score 0-100, method_used)."""
    if not transcript or not transcript.strip():
        return 0.0, "empty_answer"

    model = _try_load_embedding_model()
    if model is not None:
        try:
            embeddings = model.encode([question, transcript])
            sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return round(float(max(0, min(1, sim))) * 100, 1), "sentence-transformers"
        except Exception:
            pass  # fall through to TF-IDF

    # TF-IDF fallback — always available, no model download.
    # Blended with stemmed keyword-overlap (recall of the question's content
    # words inside the answer) because TF-IDF cosine on just two short
    # documents tends to under-score even strong answers — overlap keeps
    # the number interpretable while TF-IDF still adds some weighting for
    # word importance. Stemming (see _simple_stem) avoids penalizing an
    # answer just for using "debugging" when the question said "debug".
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf = vectorizer.fit_transform([question, transcript])
        tfidf_sim = float(cosine_similarity(tfidf[0], tfidf[1])[0][0])
    except ValueError:
        tfidf_sim = 0.0

    q_words = _content_words(question)
    a_words = _content_words(transcript)
    overlap_recall = len(q_words & a_words) / max(len(q_words), 1)

    blended = 0.35 * tfidf_sim + 0.65 * overlap_recall
    blended = max(0.0, min(1.0, blended))
    # Keyword overlap is a strict lower bound — a great answer often
    # doesn't reuse the question's exact words at all (e.g. answering
    # "how do you debug a slow script" with "profiler, vectorize, numpy").
    # A sqrt curve preserves ranking (still 0 stays 0, 1 stays 1) while
    # making partial matches feel proportionate instead of punishingly low.
    calibrated = blended ** 0.5

    score = calibrated * 100

    # Open-ended prompts ("pick a project...", "tell me about a time...")
    # can have a genuinely great, substantive answer that shares almost no
    # vocabulary with the question itself — there's no keyword to overlap
    # with. Rather than score real effort as 0, a long, real-looking answer
    # gets a small floor; a short or genuinely off-topic answer still won't
    # reach it.
    raw_word_count = len(re.findall(r"[a-z']+", transcript.lower()))
    if score < 15 and raw_word_count >= 12:
        score = 15.0

    return round(score, 1), "tfidf+overlap"


def communication_clarity_score(transcript: str) -> dict:
    """
    Returns a dict with the overall clarity score (0-100) plus the raw
    signals, so the report can explain *why* the score is what it is.
    """
    if not transcript or not transcript.strip():
        return {"score": 0.0, "filler_word_count": 0, "word_count": 0, "repeated_word_ratio": 0.0}

    text_lower = transcript.lower()
    words = re.findall(r"[a-z']+", text_lower)
    word_count = len(words)

    if word_count == 0:
        return {"score": 0.0, "filler_word_count": 0, "word_count": 0, "repeated_word_ratio": 0.0}

    filler_count = sum(text_lower.count(f) for f in _FILLER_WORDS)
    filler_ratio = filler_count / max(word_count, 1)

    # repeated-word ratio: how often the same word repeats back-to-back (a stutter/restart signal)
    repeats = sum(1 for i in range(1, len(words)) if words[i] == words[i - 1])
    repeated_ratio = repeats / max(word_count, 1)

    # Too short an answer is also a clarity problem (can't structure a thought in 3 words)
    length_penalty = 0 if word_count >= 15 else (15 - word_count) * 2

    score = 100
    score -= filler_ratio * 200      # heavy penalty for filler-word-dense speech
    score -= repeated_ratio * 150
    score -= length_penalty
    score = max(0, min(100, score))

    return {
        "score": round(score, 1),
        "filler_word_count": filler_count,
        "word_count": word_count,
        "repeated_word_ratio": round(repeated_ratio, 3),
    }


DEFAULT_WEIGHTS = {
    "technical": 30.0,
    "communication": 20.0,
    "confidence": 15.0,
    "body_language": 10.0,
    "custom": 15.0,
    "awareness": 10.0,
}

_TECHNICAL_TYPES = {"technical", "project", "behavioral"}


def aggregate_scores(answers: list[dict], weights: dict | None = None, body_language_score: float | None = None) -> dict:
    """
    answers: list of {"type": str, "relevance_score": float|None, "clarity_score": float|None,
                       "confidence_score": float|None}
    weights: category -> weight (percent). Missing categories fall back to DEFAULT_WEIGHTS.
    body_language_score: a single 0-100 score for the whole session (or None if not assessed).

    Returns {"overall_score": float, "breakdown": {category: float|None}}
    Categories with no data are excluded entirely and the remaining weights
    are renormalized — a candidate is never penalized for an optional
    module (like body language) simply not being set up.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    technical_scores = [a["relevance_score"] for a in answers if a.get("type") in _TECHNICAL_TYPES and a.get("relevance_score") is not None]
    custom_scores = [a["relevance_score"] for a in answers if a.get("type") == "custom" and a.get("relevance_score") is not None]
    awareness_scores = [a["relevance_score"] for a in answers if a.get("type") == "awareness" and a.get("relevance_score") is not None]
    clarity_scores = [a["clarity_score"] for a in answers if a.get("clarity_score") is not None]
    confidence_scores = [a["confidence_score"] for a in answers if a.get("confidence_score") is not None]

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    breakdown = {
        "technical": avg(technical_scores),
        "communication": avg(clarity_scores),
        "confidence": avg(confidence_scores),
        "body_language": round(body_language_score, 1) if body_language_score is not None else None,
        "custom": avg(custom_scores),
        "awareness": avg(awareness_scores),
    }

    present = {k: v for k, v in breakdown.items() if v is not None}
    if not present:
        return {"overall_score": None, "breakdown": breakdown}

    weight_sum = sum(weights[k] for k in present)
    overall = sum(present[k] * weights[k] for k in present) / weight_sum if weight_sum else None

    return {"overall_score": round(overall, 1) if overall is not None else None, "breakdown": breakdown}
