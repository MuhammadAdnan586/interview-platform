"""
voice_analysis.py
-------------------
Two responsibilities:

  1. transcribe_audio() — converts a recorded answer (audio file) to text.
     Uses faster-whisper (free, runs locally, no API key) if installed.
     On first use it downloads a small model (~75MB) from Hugging Face —
     that's a one-time, one-machine cost, not a per-request API call.
     If faster-whisper isn't installed or the model can't be fetched
     (e.g. no internet), we fail loudly with a clear message rather than
     guessing — a wrong transcript would corrupt every score downstream.

  2. voice_confidence_score() — analyzes the raw audio (independent of
     transcription) for pace, pitch variation, and pause patterns using
     librosa. This is pure signal processing — always available, no
     model/download needed.
"""

import numpy as np

_whisper_model = None
_whisper_load_attempted = False
_WHISPER_MODEL_SIZE = "base"  # tiny/base/small — base is a good accuracy/speed balance on CPU


def _try_load_whisper():
    global _whisper_model, _whisper_load_attempted
    if _whisper_load_attempted:
        return _whisper_model
    _whisper_load_attempted = True
    try:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(_WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    except Exception:
        _whisper_model = None
    return _whisper_model


def transcribe_audio(file_path: str) -> dict:
    """
    Returns {"transcript": str, "available": bool, "message": str}
    available=False means speech-to-text isn't set up on this machine —
    callers should fall back to asking for a typed answer instead.
    """
    model = _try_load_whisper()
    if model is None:
        return {
            "transcript": "",
            "available": False,
            "message": "Speech-to-text isn't set up. Install with: pip install faster-whisper "
                       "(requires an internet connection on first run to download the model).",
        }

    try:
        segments, _ = model.transcribe(file_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        return {"transcript": text.strip(), "available": True, "message": "ok"}
    except Exception as e:
        return {"transcript": "", "available": False, "message": f"Transcription failed: {e}"}


def voice_confidence_score(file_path: str) -> dict:
    """
    Heuristic confidence signal from raw audio:
      - speaking pace (rough words/sec proxy via voiced-frame ratio)
      - pitch variation (monotone vs expressive — too little OR too much is penalized)
      - long-pause ratio (hesitation signal)

    Returns {"score": 0-100, "available": bool, "details": {...}, "message": str}
    """
    try:
        import librosa
    except ImportError:
        return {
            "score": None,
            "available": False,
            "details": {},
            "message": "Voice tone analysis isn't set up. Install with: pip install librosa soundfile",
        }

    try:
        y, sr = librosa.load(file_path, sr=16000, mono=True)
        duration = len(y) / sr
        if duration < 0.5:
            return {"score": None, "available": False, "details": {}, "message": "Audio too short to analyze."}

        # Pitch variation
        f0, voiced_flag, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"))
        voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
        pitch_std = float(np.std(voiced_f0)) if len(voiced_f0) > 5 else 0.0
        voiced_ratio = float(np.sum(voiced_flag)) / max(len(voiced_flag), 1) if voiced_flag is not None else 0.0

        # Pause detection via RMS energy — frames below a low-energy threshold count as silence
        rms = librosa.feature.rms(y=y)[0]
        silence_threshold = np.percentile(rms, 20)
        silence_ratio = float(np.sum(rms < silence_threshold)) / max(len(rms), 1)

        # --- Scoring heuristics ---
        # Pitch: too flat (monotone, low std) or wildly erratic both hurt. Sweet spot ~10-40 Hz std.
        if pitch_std < 5:
            pitch_score = 40 + pitch_std * 4          # monotone delivery
        elif pitch_std <= 40:
            pitch_score = 90
        else:
            pitch_score = max(40, 90 - (pitch_std - 40))

        # Voiced ratio: too low means long silences/hesitation dominate the clip
        voiced_score = min(100, voiced_ratio * 130)

        # Silence ratio: some pausing is natural; above ~45% starts looking like hesitation
        silence_score = 100 if silence_ratio < 0.25 else max(30, 100 - (silence_ratio - 0.25) * 200)

        overall = round(0.4 * pitch_score + 0.3 * voiced_score + 0.3 * silence_score, 1)
        overall = max(0.0, min(100.0, overall))

        return {
            "score": overall,
            "available": True,
            "details": {
                "duration_seconds": round(duration, 1),
                "pitch_variation_hz": round(pitch_std, 1),
                "voiced_ratio": round(voiced_ratio, 2),
                "silence_ratio": round(silence_ratio, 2),
            },
            "message": "ok",
        }
    except Exception as e:
        return {"score": None, "available": False, "details": {}, "message": f"Voice analysis failed: {e}"}
