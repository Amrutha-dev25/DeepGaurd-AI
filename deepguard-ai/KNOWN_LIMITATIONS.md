# Known Limitations

No system is perfect, and DeepGuard AI is no exception. This document transparently documents every known limitation, why it exists, and how it affects you. These are **tracked, intentional trade-offs** — not bugs. We believe honesty about where we fall short is the only way to build trust.

---

## 1. Sightengine Free Tier Quota

DeepGuard AI uses **Sightengine** as its primary deepfake detection engine. The free tier is limited to approximately **500 requests per day**.

⚠️ **What happens when the quota is exhausted?**  
The pipeline automatically falls through to LLM-based fallback models in this order:  
`NVIDIA Omni → NVIDIA Nano → Gemini → Inconclusive`

**Why this matters:** The fallback models are measurably **less accurate** for deepfake detection than Sightengine. Sightengine is purpose-built for media forensics; the LLM fallbacks are general-purpose vision models applied to a task they weren't specifically trained for.

**Effect on users:**
- During demos or heavy evaluation sessions, hitting the quota will produce lower-confidence results.
- Batch analysis of many files in succession will exhaust the quota faster.
- Evaluation benchmarks that process many samples may show degraded accuracy simply due to fallback model usage.

💡 **Note:** You can monitor your current Sightengine usage in the application logs. The quota resets daily.

---

## 2. Groq Free Tier Token Limits

**Groq** powers two components of DeepGuard AI:
- **Router LLM** — decides which analysis path to take
- **Report LLM** — generates the final human-readable analysis report

The Groq free tier allows **100,000 tokens per day (TPD)** across all requests.

⚠️ **What happens when the limit is reached?**  
The pipeline falls back through:  
`NVIDIA Omni → Gemini → Deterministic fallback`

The **deterministic fallback** produces template-based reports with no LLM reasoning. While the analysis results (Sightengine scores, frame-level data) remain accurate, the quality of the written report degrades significantly.

💡 **Note:** Report generation uses more tokens than routing, so the limit is typically exhausted by report generation first. This means the Router usually stays on Groq longer than the Report LLM.

---

## 3. Video Accuracy — Currently 30%

This is the single largest accuracy gap in DeepGuard AI today.

| Modality | Accuracy |
|----------|----------|
| Images   | **100%** (10/10) |
| Videos   | **30%** (3/10) |
| **Overall** | **65%** (13/20) |

*Source: [`eval_dataset/results.md`](eval_dataset/results.md)*

**Why video accuracy is low:**

1. **Key frame extraction:** Sightengine only analyzes **5 key frames** extracted from the full video. A deepfake artifact may only appear in frames that are not among the 5 extracted, causing a miss.
2. **Worst-first aggregation:** The pipeline aggregates per-frame scores using a "worst-first" heuristic (the most suspicious frame drives the final verdict). This creates inconsistency — genuine artifacts in one frame can dominate even if the rest of the video is clean.
3. **No temporal analysis:** The current pipeline does not analyze motion patterns, lip-sync consistency, or frame-to-frame anomalies that human reviewers and specialized video forensics tools look for.

**Planned improvements:**
- Increase the number of extracted key frames (adaptive sampling based on video length).
- Implement temporal coherence checks between frames.
- Explore frame-by-frame analysis with sequence-aware models.

---

## 4. Network Failures

DeepGuard AI makes API calls to multiple external services (Sightengine, Groq, NVIDIA, Gemini). Network interruptions — even brief ones — cause individual requests to fail.

⚠️ **What happens?**  
The failed request falls through the fallback chain to the next available model. In the worst case, the entire chain can fail, landing on the **deterministic fallback**.

**Consequences:**
- Lower-confidence models are used instead of the primary.
- The deterministic fallback provides no ML-based analysis at all.
- Results may vary between runs depending on network conditions at the time of each API call.

**System stability is not affected.** The pipeline always completes and returns a result. The question is only *which model* produces that result.

💡 **Note:** Retry logic is implemented, but transient failures that persist beyond retry limits will trigger fallback progression.

---

## 5. Frontend Placeholder Data

The dashboard telemetry displayed in the frontend — including the "12,482 scans handled" counter and similar statistics — uses **hardcoded placeholder values**.

⚠️ These numbers are **not** live analytics. They were added as visual filler during development to demonstrate the UI layout.

**What this means:**
- The counter does not reflect actual scan volume.
- No usage analytics or real-time telemetry pipeline is connected to the frontend.
- All dashboard stats (scans handled, accuracy percentages, etc.) remain static.

This is purely a **frontend cosmetics** limitation. The backend analysis pipeline is fully functional. Real telemetry integration is a planned enhancement.

---

## 6. No ML Ensemble / Classifier Fusion

DeepGuard AI uses a **linear fallback chain**: try Sightengine first, and if it fails or is unavailable, try the next model in sequence. There is **no ensemble voting, weighted fusion, or meta-classifier** that combines signals from multiple models.

**Why this exists:** The current architecture prioritizes simplicity and predictable latency. Ensemble methods require:
- All models to run in parallel (increasing cost and latency)
- A trained fusion classifier (requiring labeled data and ML engineering)
- Normalized confidence scoring across heterogeneous models (Sightengine scores are not directly comparable to LLM probabilities)

**Effect on accuracy:** When Sightengine is available, the pipeline performs well (100% on images). But in fallback scenarios, the system relies entirely on a single fallback model rather than combining signals from multiple models to reach a consensus.

---

## 7. No EXIF-Based AI Tool Detection

DeepGuard AI does not currently perform **data-driven EXIF analysis** to detect AI-generated content signatures embedded in file metadata. While EXIF parsing is available in the codebase, it is not used as an investigative signal.

**Why:** EXIF-based detection requires a trained classifier over known AI-tool metadata patterns (e.g., specific encoder signatures from Stable Diffusion, Midjourney, DALL-E). Building and maintaining this classifier requires continual data collection as new AI tools emerge.

💡 **Note:** EXIF metadata is still surfaced in raw analysis output when available — it is simply not used as an *input feature* for the deepfake classifier decision.

---

## Conclusion

Every limitation listed here affects **evaluation accuracy** (how often the system correctly identifies deepfakes). **None of them affect system stability** — the pipeline never crashes, hangs, or fails to return a result.

If you are evaluating DeepGuard AI:
- Be aware of daily API quotas — they will affect multi-run evaluations.
- Video results should be interpreted with caution at this stage.
- Dashboard stats are not real — use the backend API directly for ground truth.

We track all of these items openly and will update this document as improvements are made. For detailed evaluation results, see [`eval_dataset/results.md`](eval_dataset/results.md).
