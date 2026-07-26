# tools/

Individual forensic analysis functions. Each tool examines one specific thing about a file
— compression artifacts, metadata, noise patterns, copied regions, etc. The results from
all tools are bundled together as "forensic context" for the analysis agent.

## Files

- **ela.py** — Error Level Analysis: re-saves the image at a known JPEG quality and
  highlights areas where compression error differs from the original.
- **exif.py** — EXIF metadata extraction: camera model, software, GPS coordinates,
  timestamps. Flags inconsistencies like "created before the camera model existed."
- **fft.py** — Frequency domain analysis: converts image to frequency space and measures
  the ratio of high-frequency energy (useful for detecting GAN blur).
- **noise.py** — Noise analysis: computes Laplacian variance across the image.
  Generative images often have unnatural noise patterns.
- **jpeg.py** — JPEG artifact detection: measures block boundary ratios to see if the
  image was re-saved or spliced from multiple sources.
- **clone.py** — Clone detection: uses ORB keypoint matching to find duplicated regions
  (copy-move forgery).
- **forensics.py** — Face detection (Haar cascade) and image hashing (SHA-256 for
  integrity, pHash for perceptual matching). Also exports `collect_forensic_context()`
  which runs all tools and bundles their output.
- **security.py** — PII redaction and prompt injection detection. Exported as
  `security_checkpoint()` and `security_tools` for guard use.
- **search.py** — Tavily web search integration (optional, off by default). Used by
  the report agent to find context about known deepfake incidents.
- **temporal.py** — Video temporal analysis: computes frame-to-frame differences, motion
  scores, and detects scene changes. Helps spot temporal artifacts in generated video.

## Walkthrough

The most important file is **forensics.py**. It acts as the orchestrator:

1. `collect_forensic_context()` is called with the image path
2. It runs ELA → EXIF → FFT → Noise → JPEG → Clone → Face Detection in sequence
3. Each tool's result is a dict — they're merged into one big forensic context dict
4. That dict is returned to the caller (router agent or analysis agent)
