# preprocessing/

Code that prepares raw uploaded files for forensic analysis. Images and videos go
through different pipelines — but both end up as a standardized set of data that the
tools and agents can work with.

## Files

- **image_pipeline.py** — `run_image_pipeline()`: takes a raw image, resizes it,
  applies CLAHE for contrast enhancement, denoises, runs ELA + FFT + DCT + wavelet
  transforms, generates edge maps, and computes hashes (SHA-256 + pHash). Returns a
  dict of all derived data.
- **video_pipeline.py** — `run_video_pipeline()`: takes a raw video, extracts key
  frames adaptively (more frames during scene changes), tracks faces across frames,
  computes optical flow vectors, and selects the most informative frames for analysis.
  Returns extracted frames + motion metadata + face tracks.

## Walkthrough

### image_pipeline.py (the primary pipeline)

1. Raw image bytes arrive from the upload endpoint
2. Pipeline resizes the image to a standard working resolution
3. Applies CLAHE to bring out details in dark/bright areas
4. Denoises to reduce camera sensor noise
5. Runs the forensic transforms: Error Level Analysis, FFT spectrum, DCT coefficients,
   wavelet decomposition, Canny edge detection
6. Computes SHA-256 (integrity) and perceptual hash (similarity matching)
7. Returns a single dict with all preprocessed data, ready for the tools and agents
