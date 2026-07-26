"""Preprocessing pipeline — pure computer vision, no LLMs.

Image pipeline: resize, normalize, RGB, face crop, CLAHE, denoise,
  ELA, FFT, DCT, wavelet, edge maps, metadata, hashing.

Video pipeline: frame extraction, face tracking, temporal sampling,
  optical flow, quality filtering, keyframe detection.
"""

from .image_pipeline import run_image_pipeline
from .video_pipeline import run_video_pipeline

__all__ = ["run_image_pipeline", "run_video_pipeline"]
