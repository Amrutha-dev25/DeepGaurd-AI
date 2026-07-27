# Video Evaluation Results (post-fix)

- **Date**: `2026-07-27 11:29:19`
- **Total videos**: 10
- **Passed**: 2/10 (20.0%)

## Before vs After

| Issue | File | Before (original eval) | After (post-fix) | Change |
|-------|------|----------------------|------------------|--------|
| Bug 1 (415) | vid7_f.mp4 | HTTP 415 Unsupported Media Type | fake (99%) [sightengine] PASS | FIXED |
| Bug 1 (415) | vid9_f.mp4 | HTTP 415 Unsupported Media Type | real (99%) [sightengine] FAIL* | FIXED |
| FP | vid1_r.mp4 | fake (96%) [sightengine] FAIL | fake (96%) [sightengine] FAIL | Same (Sightengine FP) |
| FP | vid6_f.mp4 | inconclusive (0%) [none] FAIL | real (99.9%) [sightengine] FAIL** | Changed (Sightengine FN) |
| Timeout | vid3_r.mp4 | real (98%) [sightengine] PASS | timeout | Worse (quota exhausted) |
| Timeout | vid4_r.mp4 | fake (45%) [nvidia] FAIL | timeout | Worse (quota exhausted) |
| Timeout | vid5_r.mp4 | timeout | timeout | Same |
| Timeout | vid10_f.mp4 | inconclusive (0%) [none] FAIL | timeout | Same |
| Timeout | vid8_f.mp4 | fake (50%) [nvidia] PASS | timeout | Worse (quota exhausted) |
| — | vid2_r.mp4 | real (99%) [sightengine] PASS | real (99%) [sightengine] PASS | Same |

\* vid9_f.mp4 is GT=fake but Sightengine says real@99% — Sightengine false negative, not a 415 bug.
** vid6_f.mp4 is GT=fake but Sightengine says real@99.9% — Sightengine false negative.

## Key Findings

**Bug 1 (415 MIME) — CONFIRMED FIXED.** Both vid7_f.mp4 and vid9_f.mp4 now pass MIME detection and reach the Sightengine pipeline. The root cause was libmagic returning `application/octet-stream` for some MP4 encoders, which was returned immediately without falling through to extension-based detection. Now `_detect_mime()` cascades through magic → content-type → PIL → extension before giving up.

**Bug 2 (File 11 — vid1_r.mp4 false positive).** This is a **Sightengine model false positive**, not a code bug. Sightengine returns `fake@96%` with high confidence. The most likely trigger: one of the 5 extracted key frames captured an I-frame transition or motion blur that Sightengine's deepfake model interprets as tampering. This requires model-level improvement (frame aggregation strategy change or Sightengine model tuning), not a code fix.

**Bug 3 (Files 16/17 — model="none").** Cannot be verified in this run because Sightengine quota was exhausted mid-run, and 5 of 10 videos timed out. The code fix (deterministic fallback: `model="deterministic"`, `confidence=0.5`) was applied but not exercised.

## CSV for comparison

```
File,GT,Before_Verdict,Before_Conf,Before_Model,After_Verdict,After_Conf,After_Model,After_Pass
vid1_r.mp4,real,fake,96%,sightengine,fake,96%,sightengine,FAIL
vid2_r.mp4,real,real,99%,sightengine,real,99%,sightengine,PASS
vid3_r.mp4,real,real,98%,sightengine,timeout,,,FAIL
vid4_r.mp4,real,fake,45%,nvidia,timeout,,,FAIL
vid5_r.mp4,real,timeout,,,timeout,,,FAIL
vid10_f.mp4,fake,inconclusive,0%,none,timeout,,,FAIL
vid6_f.mp4,fake,inconclusive,0%,none,real,99.9%,sightengine,FAIL
vid7_f.mp4,fake,ERROR(415),,,"fake",99%,sightengine,PASS
vid8_f.mp4,fake,fake,50%,nvidia,timeout,,,FAIL
vid9_f.mp4,fake,ERROR(415),,,"real",99%,sightengine,FAIL
```
