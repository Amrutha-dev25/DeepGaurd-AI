# DeepGuard AI — Agentic Supervisor Implementation Spec

> Locked spec document capturing all review rounds, accepted decisions,
> rejected proposals with reasons, and the final implementation state.

## Scope discipline

This spec went through several review rounds. Some proposals were accepted,
some were explicitly rejected after checking them against actual code and
prior findings. **Do not reintroduce rejected items** "to be safe" or
"for completeness." Each rejection is listed with the reason.

### Rejected, and why

- **A forensic-evidence fusion gate that skips Sightengine entirely** when
  ELA/FFT/noise/metadata look strongly one-sided. The codebase already tried
  a version of this — blending heuristic forensic votes into the decision —
  and removed it, with a comment stating it "was never validated against
  labeled data and was actively making the calibrated confidence worse."
  Moving that same unvalidated logic earlier in the pipeline, with the power
  to skip the most reliable signal, is a bigger version of the same mistake.
  The analysis_agent.py instruction also states the ELA/noise reference ranges
  are "NOT thresholds, they are calibration anchors" — using them as a hard
  skip-gate contradicts that.

- **Supervisor self-rated confidence score** (e.g. "CONCLUDE, confidence
  0.82"). No calibration data backs a number like that; same failure mode
  as the fusion formula already removed.

- **Provider voting / majority-wins.** Three vision-LLM opinions often share
  the same blind spots since they are looking at the same image — a vote
  treats them as independent when they aren't. Not implemented until eval
  data shows which provider is actually more reliable for which failure mode.

- **Parallel-fire all providers, then reason over all results.** Defeats
  the entire cost-aware point of this design. Every case pays for three
  calls even when one would have sufficed.

- **9-tool catalog, case-memory database, Tool→Critic→Supervisor reflection
  loop.** Not built because there is no infrastructure for them yet and they
  are not needed to demonstrate real agentic decision-making. Note them in
  a PR as "designed, deferred" — that reads as better judgment than building
  them unnecessarily.

### Accepted

- **Capability abstraction** — supervisor reasons about *what kind* of
  evidence it needs, runtime maps that to a specific provider. Keeps the
  supervisor's reasoning about evidence, not infrastructure.

- **Corroboration-extended confidence gate** — this is the real answer to
  "what if strong evidence appears first," and it is earned by data already
  trusted, not a new unvalidated heuristic.

- **Disagreement-first supervisor reasoning** — the supervisor's central
  question is "what's unresolved, and would anything I have left resolve it,"
  not "confidence is low, get another opinion."

## Standing rule: fact vs. decision

Before accepting any new piece of code into the analysis/supervisor path,
ask: **does this code output a fact (a labeled value handed to a model) or
a decision (CONCLUDE/GET_SECOND_OPINION/INCONCLUSIVE_STOP/a verdict) without
a model call in between?** Facts are fine and necessary — labeling a metric's
reliability, flagging missing evidence, computing an agreement count.
Decisions made by code instead of the supervisor are the rejected pattern
that has shown up three times already. This test is what to apply going
forward instead of re-deriving it each time.

## Architecture decisions

### Supervisor provider

**Final decision: Gemini only.** Three rounds of chasing a fourth,
fully-separate free provider (NVIDIA NIM — shared quota with Omni/Nano,
ruled out; Cerebras — archived model, then billing wall) cost more debugging
time than they saved. Gemini is confirmed working in production logs (both
rounds succeeded, real reasoning, ~14s each), requires no card, and is
already integrated.

```
Supervisor Primary   → Gemini (gemini-2.5-flash)
# No fallback tier — if Gemini is down, best-available-evidence infra-fallback applies
```

### Convergence enforcement

`_check_convergence()` may compute agreement/split status, but it must not
return CONCLUDE or INCONCLUSIVE_STOP. It returns a status string
(`"AGREE"` / `"SINGLE_OPINION"` / `"SPLIT"` / `"PARTIAL"`) that gets folded
into the `build_supervisor_context()` "AGREEMENT CONTEXT" block. The
supervisor's own JSON `action` field remains the only source of CONCLUDE /
GET_SECOND_OPINION / INCONCLUSIVE_STOP.

### Evidence sufficiency gate

Sightengine is the first and only paid call before any reasoning happens.
Two conditions, both grounded in Sightengine's own calibrated output:

1. **Case A (≥0.8)**: Return Sightengine verdict directly — no LLM call.
2. **Case B (0.55–0.79 with forensic corroboration)**: Return Sightengine
   verdict directly if ≥3 of available forensic signals independently point
   the same direction. This is corroboration of an already-trusted signal,
   not a replacement for it — never runs before Sightengine.
3. **Below threshold or conflicting**: Enter the supervisor loop.

### Metric reliability caveats

`_metric_caveat()` is a source-agnostic, server-side function that computes
a labeled reliability tag per forensic metric. Facts only — no decision
made by code. Currently applies to video-recompression-affected metrics;
extensible as new patterns are discovered. Unavailable metrics (None due to
computation failure) are labeled `"unavailable"` explicitly rather than
silently omitted.

### Agreement accounting

Only directional (real/fake) verdicts are counted for convergence. Inconclusive
entries represent abstention — they are not evidence of agreement. When
fewer than 2 directional opinions exist, the status is `"SINGLE_OPINION"`
with explicit text, never `"AGREE"`.

## Key files

| File | Role |
|------|------|
| `backend/app/runner.py` | Control flow: evidence gate, supervisor loop, infra-fallback, caveat system |
| `backend/app/agents/supervisor_agent.py` | Supervisor agent factory, prompt, context builder, direction calculator |
| `backend/app/config.py` | Model settings: `supervisor_primary_model`, `supervisor_fallback_model` |
| `backend/app/api.py` | Startup logging for Supervisor config |
| `backend/app/agents/report_agent.py` | Report generation (untouched by supervisor changes) |
| `docs/agentic-supervisor-spec.md` | This file |
