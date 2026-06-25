"""
body_language.py
------------------
OPTIONAL module (Phase 4). Analyzes a short webcam video clip for three
supportive signals — never a pass/fail judgment, just descriptive feedback:

  - eye_contact_pct   : % of sampled frames where the face is roughly
                        forward-facing toward the camera
  - posture_score     : shoulder-level alignment (proxy for slouching/tilt)
  - hand_movement     : classified as "low" / "moderate" / "high"

Why this is optional and isolated:
  - Requires two MediaPipe model files (~10MB total) downloaded once —
    see README "Phase 4 setup". Without them, this module returns
    available=False and the rest of the app works exactly the same;
    body language simply shows as "Not assessed" in the report instead
    of blocking anything.
  - We deliberately do NOT score "dressing" or attractiveness, and we do
    NOT output a single judgmental number for body language — only
    descriptive, coachable signals (see README/Phase 4 ethics note).
"""

import os
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
POSE_MODEL_PATH = os.path.join(MODELS_DIR, "pose_landmarker_lite.task")
FACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_landmarker.task")

_SAMPLE_FPS = 2  # analyze ~2 frames per second of video — plenty for posture/gaze trends


def _models_available() -> bool:
    return os.path.isfile(POSE_MODEL_PATH) and os.path.isfile(FACE_MODEL_PATH)


def analyze_video(file_path: str) -> dict:
    """
    Returns:
      {
        "available": bool,
        "message": str,
        "eye_contact_pct": float | None,
        "posture_score": float | None,
        "hand_movement": str | None,   # "low" | "moderate" | "high"
        "frames_analyzed": int,
      }
    """
    if not _models_available():
        return {
            "available": False,
            "message": (
                "Body language analysis isn't set up. This is optional — see README "
                "'Phase 4 setup' for the two model files to download (~10MB, one-time)."
            ),
            "eye_contact_pct": None,
            "posture_score": None,
            "hand_movement": None,
            "frames_analyzed": 0,
        }

    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
    except Exception as e:
        return {
            "available": False,
            "message": f"Required libraries not installed (pip install mediapipe opencv-python): {e}",
            "eye_contact_pct": None, "posture_score": None, "hand_movement": None, "frames_analyzed": 0,
        }

    try:
        pose_options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=POSE_MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
        )
        face_options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=FACE_MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=1,
        )

        cap = cv2.VideoCapture(file_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(video_fps / _SAMPLE_FPS))

        forward_facing_count = 0
        faces_detected = 0
        shoulder_tilts = []
        wrist_positions = []
        frame_idx = 0
        frames_analyzed = 0

        with mp_vision.PoseLandmarker.create_from_options(pose_options) as pose_landmarker, \
             mp_vision.FaceLandmarker.create_from_options(face_options) as face_landmarker:

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval != 0:
                    frame_idx += 1
                    continue
                frame_idx += 1
                frames_analyzed += 1

                rgb_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame[:, :, ::-1].copy())

                # --- Face / gaze proxy ---
                face_result = face_landmarker.detect(rgb_frame)
                if face_result.face_landmarks:
                    faces_detected += 1
                    lm = face_result.face_landmarks[0]
                    # rough yaw proxy: horizontal symmetry of landmarks 234 (left cheek) / 454 (right cheek)
                    nose_x = lm[1].x
                    left_x, right_x = lm[234].x, lm[454].x
                    mid = (left_x + right_x) / 2
                    yaw_deviation = abs(nose_x - mid) / max(abs(right_x - left_x), 1e-6)
                    if yaw_deviation < 0.18:  # roughly centered -> "facing camera"
                        forward_facing_count += 1

                # --- Pose / posture + hand movement ---
                pose_result = pose_landmarker.detect(rgb_frame)
                if pose_result.pose_landmarks:
                    lm = pose_result.pose_landmarks[0]
                    left_shoulder, right_shoulder = lm[11], lm[12]
                    shoulder_tilts.append(abs(left_shoulder.y - right_shoulder.y))

                    left_wrist, right_wrist = lm[15], lm[16]
                    wrist_positions.append((left_wrist.x, left_wrist.y, right_wrist.x, right_wrist.y))

        cap.release()

        if frames_analyzed == 0:
            return {
                "available": False, "message": "Could not read any frames from the video file.",
                "eye_contact_pct": None, "posture_score": None, "hand_movement": None, "frames_analyzed": 0,
            }

        eye_contact_pct = round(100 * forward_facing_count / max(faces_detected, 1), 1) if faces_detected else None

        posture_score = None
        if shoulder_tilts:
            avg_tilt = float(np.mean(shoulder_tilts))
            posture_score = round(max(0, 100 - avg_tilt * 500), 1)  # flatter shoulders -> higher score

        hand_movement = None
        if len(wrist_positions) > 3:
            arr = np.array(wrist_positions)
            movement_variance = float(np.mean(np.std(arr, axis=0)))
            if movement_variance < 0.02:
                hand_movement = "low"
            elif movement_variance < 0.06:
                hand_movement = "moderate"
            else:
                hand_movement = "high"

        return {
            "available": True,
            "message": "ok",
            "eye_contact_pct": eye_contact_pct,
            "posture_score": posture_score,
            "hand_movement": hand_movement,
            "frames_analyzed": frames_analyzed,
        }

    except Exception as e:
        return {
            "available": False, "message": f"Body language analysis failed: {e}",
            "eye_contact_pct": None, "posture_score": None, "hand_movement": None, "frames_analyzed": 0,
        }
