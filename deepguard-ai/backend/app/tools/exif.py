"""EXIF metadata extraction tool."""

from pathlib import Path
from typing import Any

import exifread
from google.adk.tools import FunctionTool

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
_AI_KEYWORDS = ["stable diffusion", "midjourney", "comfyui", "leonardo.ai", "dall-e", "dalle", "flux", "adobe firefly", "dreamstudio"]
_EDITING_KEYWORDS = ["photoshop", "gimp", "lightroom", "affinity"]


def extract_exif(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    if path.suffix.lower() in _VIDEO_EXTENSIONS:
        return {"tag_count": 0, "tags": {}, "editing_software": [], "ai_generation_tools": [], "evidence": "EXIF metadata is not applicable for video files."}
    with open(file_path, "rb") as fh:
        tags = exifread.process_file(fh, details=False)
    exif_data = {str(k): str(v) for k, v in tags.items()}
    software_tags = [v.lower() for k, v in exif_data.items() if k.lower() in ("image software", "software", "image processing")]
    editing_found = [kw for kw in _EDITING_KEYWORDS for tag in software_tags if kw in tag]
    ai_found = [kw for kw in _AI_KEYWORDS for tag in software_tags if kw in tag]
    evidence = f"Found {len(exif_data)} EXIF tag(s)."
    if editing_found:
        evidence += f" Editing software detected: {', '.join(set(editing_found))}."
    if ai_found:
        evidence += f" AI-generation tool detected: {', '.join(set(ai_found))}."
    if not editing_found and not ai_found:
        evidence += " No known editing or AI-generation markers found."
    return {
        "tag_count": len(exif_data),
        "tags": {k: v for k, v in exif_data.items() if k not in ("JPEGThumbnail",)},
        "editing_software": list(set(editing_found)),
        "ai_generation_tools": list(set(ai_found)),
        "evidence": evidence,
    }


exif_tool = FunctionTool(func=extract_exif)
