# DeepGuard AI — Project Status

## Overview

Real-time deepfake detection pipeline. Video/image upload → Sightengine analysis → Supervisor-driven loop → Report generation. All agents use Google ADK.

## Architecture (current)

```
Upload → Guardrails → Router → Sightengine (Primary Detector)
                                         ↓
                              Evidence Sufficiency Gate
                              ├─ conf ≥ 0.8 → fast return
                              └─ conf < 0.8 → Supervisor Loop
                                               ↓
                                    Supervisor (Gemini 2.5 Flash)
                                    ├─ CONCLUDE → use best evidence
                                    ├─ GET_SECOND_OPINION → dispatch analysis agent
                                    └─ INCONCLUSIVE_STOP → return inconclusive
                                               ↓
                                         Report (Groq)
```

## Provider Chain

### Router: Groq → NVIDIA Omni → NVIDIA Nano → Gemini → Deterministic
### Analysis: Sightengine (REST) → [Supervisor dispatches:] NVIDIA Ommi / NVIDIA Nano / Gemini
### Supervisor: Gemini 2.5 Flash (sole provider — Cerebras removed)
### Report: Groq → NVIDIA Omni → NVIDIA Nano → Gemini → Deterministic

## Agent Design Decisions

| Decision | Status |
|----------|--------|
| Cerebras removed (billing wall, archived models) | ✅ Done |
| Gemini is sole supervisor provider | ✅ Done |
| `FALLBACK_INSTRUCTION` deleted; all agents use `PRIMARY_INSTRUCTION` | ✅ Done |
| Reference ranges are one-sided (values below floor are NORMAL, not suspicious) | ✅ Done |
| Model name display fixed for native ADK string models | ✅ Done |
| Sightengine fast path at ≥ 0.8 confidence | ✅ Done |
| Evidence Sufficiency Gate (0.55–0.79 + forensic corroboration) | ✅ Done |
| Convergence detection: SINGLE_OPINION / AGREE / SPLIT / PARTIAL | ✅ Done |
| Supervisor max_rounds = 3 | ✅ Done |
| Reliability tags on forensic metrics (video recompression, high-res caveats) | ✅ Done |
| Weight-by-reliability rule (tagged metrics carry LESS weight than visual) | ✅ Done |

## Files

### Core Pipeline
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/runner.py` | Main pipeline orchestrator | ✅ |
| `backend/app/api.py` | FastAPI layer | ✅ |
| `backend/app/config.py` | Pydantic Settings | ✅ |
| `backend/app/agents/supervisor_agent.py` | Supervisor agent + build_supervisor_context | ✅ |
| `backend/app/agents/analysis_agent.py` | Analysis agent + instructions | ✅ |
| `backend/app/agents/router_agent.py` | Router agent | ✅ |
| `backend/app/agents/report_agent.py` | Report agent | ✅ |
| `backend/app/agents/provider_factory.py` | Centralized model creation | ✅ |

### Detection Providers
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/providers/sightengine.py` | Sightengine REST API client | ✅ |

### Forensics
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/tools/forensics.py` | Orchestrates all forensic tools | ✅ |
| `backend/app/tools/ela.py` | Error Level Analysis | ✅ |
| `backend/app/tools/noise.py` | Noise variance (Laplacian) | ✅ |
| `backend/app/tools/fft.py` | FFT high-frequency ratio | ✅ |
| `backend/app/tools/dct.py` | (if exists) DCT coefficient analysis | — |
| `backend/app/tools/jpeg.py` | JPEG block boundary analysis | ✅ |
| `backend/app/tools/clone.py` | Clone detection | ✅ |
| `backend/app/tools/exif.py` | EXIF metadata parsing | ✅ |
| `backend/app/tools/temporal.py` | Video frame analysis | ✅ |
| `backend/app/tools/security.py` | Injection/malware checks | ✅ |
| `backend/app/tools/search.py` | Web search (report agent tool) | ✅ |

### Preprocessing
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/preprocessing/image_pipeline.py` | Image preprocessing | ✅ |
| `backend/app/preprocessing/video_pipeline.py` | Video preprocessing | ✅ |

### Guardrails
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/guardrails/validation.py` | File validation | ✅ |
| `backend/app/guardrails/injection.py` | Injection detection | ✅ |
| `backend/app/guardrails/moderation.py` | Content moderation | ✅ |
| `backend/app/guardrails/schema.py` | Output schema validation | ✅ |

### Services
| File | Purpose | Status |
|------|---------|--------|
| `backend/app/services/report_service.py` | Report formatting | ✅ |
| `backend/app/services/audit_service.py` | Audit logging | ✅ |
| `backend/app/services/pdf_service.py` | PDF generation | ✅ |

## Verified Behaviors

- [x] Real video → Sightengine conf=0.99 → fast path → REAL verdict
- [x] Supervisor uses Gemini 2.5 Flash (no Cerebras attempt)
- [x] Router Groq primary succeeds with metadata extraction
- [x] Report Groq primary generates readable verdict text
- [x] Model names display correctly (no "unknown")

## Known Limitations

See `KNOWN_LIMITATIONS.md` for full list. Key items:
- Single-video-frame forensic analysis (DCT, wavelets, edge intensity not computed for video)
- Sightengine quota exhaustion needs handling (pool consumption)
- No timeout on individual ADK agent calls within the supervisor loop

## Next Actions

- [ ] Run eval on fake media to verify supervisor loop convergence
- [ ] Evaluate fallback analysis agents with PRIMARY_INSTRUCTION produce strong verdicts
- [ ] Consider Sightengine multi-frame aggregation improvements
- [ ] Add DCT/wavelet/edge computation for video frames
