"""Video preprocessing pipeline — pure computer vision.

Operations: frame extraction (adaptive), face tracking, temporal sampling,
optical flow, quality filtering, keyframe detection.
"""

import os
import tempfile
from typing import Any

import cv2
import numpy as np

from app.config import settings


def extract_frames_adaptive(
    file_path: str,
    max_frames: int | None = None,
    min_scene_change: float = 30.0,
) -> list[dict[str, Any]]:
    if max_frames is None:
        max_frames = settings.video_max_frames
    """Extract frames using scene-change detection and uniform sampling."""
    cap = cv2.VideoCapture(file_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if total_frames < 1:
        cap.release()
        return []

    frames: list[dict[str, Any]] = []
    prev_gray = None
    step = max(1, total_frames // max_frames)

    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_data: dict[str, Any] = {
            "index": i,
            "timestamp": i / fps if fps > 0 else 0,
            "frame": frame,
        }

        # Scene change detection
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray).mean()
            frame_data["scene_change"] = float(diff) > min_scene_change
        else:
            frame_data["scene_change"] = False

        # Blur detection (Laplacian variance)
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        frame_data["blur_score"] = float(blur)

        # Brightness
        frame_data["brightness"] = float(gray.mean())

        prev_gray = gray
        frames.append(frame_data)

    cap.release()
    return frames


def track_faces(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Track face presence across frames and tag each frame."""
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    for f in frames:
        gray = cv2.cvtColor(f["frame"], cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        f["face_count"] = len(faces)
    return frames


def select_informative_frames(
    frames: list[dict[str, Any]],
    max_output: int = 10,
) -> list[dict[str, Any]]:
    """Select the most informative frames based on blur, scene changes, and face presence."""
    if not frames:
        return []

    scored = []
    for f in frames:
        score = 0.0
        if f.get("scene_change"):
            score += 5.0
        score += f.get("face_count", 0) * 3.0
        blur = f.get("blur_score", 0)
        if blur > 50:
            score += 2.0
        else:
            score -= (50 - blur) / 50
        score += f.get("brightness", 128) / 256
        scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [f for _, f in scored[:max_output]]
    selected.sort(key=lambda x: x["index"])
    return selected


def compute_optical_flow(
    frames: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute optical flow magnitude between consecutive frames."""
    for i in range(1, len(frames)):
        prev_gray = cv2.cvtColor(frames[i - 1]["frame"], cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(frames[i]["frame"], cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        frames[i]["flow_magnitude"] = float(mag.mean())
        frames[i - 1].setdefault("flow_magnitude", 0.0)
    return frames


def extract_audio_metadata(file_path: str) -> dict[str, Any]:
    """Extract basic audio information from video file."""
    cap = cv2.VideoCapture(file_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_seconds": round(total_frames / fps, 2) if fps > 0 else 0,
    }


def run_video_pipeline(file_path: str) -> dict[str, Any]:
    """Run the full video preprocessing pipeline."""
    result: dict[str, Any] = {"status": "ok"}

    # Audio / basic metadata
    result["metadata"] = extract_audio_metadata(file_path)

    # Adaptive frame extraction (uses settings.video_max_frames)
    raw_frames = extract_frames_adaptive(file_path)
    result["total_frames_extracted"] = len(raw_frames)

    if not raw_frames:
        result["status"] = "error"
        result["error"] = "No frames could be extracted"
        return result

    # Face tracking across frames
    raw_frames = track_faces(raw_frames)
    total_faces = sum(f.get("face_count", 0) for f in raw_frames)
    result["total_faces_detected"] = total_faces

    # Compute optical flow
    raw_frames = compute_optical_flow(raw_frames)
    flow_values = [f.get("flow_magnitude", 0) for f in raw_frames if f.get("flow_magnitude")]
    result["avg_flow_magnitude"] = round(float(np.mean(flow_values)), 4) if flow_values else 0

    # Select informative frames (uses settings.video_informative_frames)
    selected = select_informative_frames(raw_frames, max_output=settings.video_informative_frames)
    result["selected_frames"] = len(selected)
    result["frame_indices"] = [f["index"] for f in selected]
    result["frame_brightness_avg"] = round(
        float(np.mean([f.get("brightness", 128) for f in selected])), 2
    )
    result["frame_blur_avg"] = round(
        float(np.mean([f.get("blur_score", 0) for f in selected])), 2
    )

    # Best frame for analysis
    if selected:
        best = max(selected, key=lambda f: (f.get("face_count", 0) * 10 + (f.get("blur_score", 0) > 50) * 5))
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        cv2.imwrite(tmp_path, best["frame"])
        with open(tmp_path, "rb") as f:
            result["best_frame_bytes"] = f.read()
        os.unlink(tmp_path)
        result["best_frame_index"] = best["index"]

    return result
