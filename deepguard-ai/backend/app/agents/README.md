# agents/

The agents make decisions about uploaded media. Each agent gets evidence, talks to a
language model, and returns a structured result. The agents form a pipeline with an
investigation loop: one classifies, one analyzes, one supervises, one reports.

## Files

- **provider_factory.py** — Single place where every agent gets its LLM model. Agents
  just say "give me provider X" and get back a ready-to-use LiteLlm or Gemini instance.
- **router_agent.py** — ADK agent that decides what the file _is_ (photo, document, video)
  and whether it _can_ be analyzed. Never predicts fake/real — just routes.
- **analysis_agent.py** — Agent that concludes REAL / FAKE / INCONCLUSIVE. Gets
  forensic data + Sightengine result + a detailed forensic instruction prompt. Called
  once per round by the Supervisor loop; each round may use a different capability.
- **supervisor_agent.py** — Evidence-driven decision agent. Does NOT analyze media.
  Decides whether to CONCLUDE (sufficient evidence), request GET_SECOND_OPINION
  (specific capability needed), or INCONCLUSIVE_STOP (no resolution possible).
  Runs inside a bounded loop (max 2 rounds). Reasons about capabilities only,
  never sees provider or model names.
- **report_agent.py** — Takes the verdict and evidence and writes a human-readable forensic
  report. Never re-decides — just narrates. Can optionally search the web via Tavily.

## Walkthroughs

### provider_factory.py

1. An agent requests a model by name (e.g. `"nvidia-omni"`)
2. `ProviderFactory` looks up the config for that provider (API key, model name, params)
3. Creates a `LiteLlm` instance (or a `Gemini` instance for Gemini models)
4. Returns the ready-to-call model object to the requesting agent

### router_agent.py

1. Receives the uploaded file's metadata + precomputed forensic context
2. Calls `validate_upload()` to reject dangerous files (wrong extension, too large, etc.)
3. Calls `detect_faces()` to check if human faces are present in the image
4. Classifies media type (photo/video/document) and decides whether analysis is viable
5. Returns a JSON routing decision: media type, face count, viability flag

### analysis_agent.py

1. Receives the preprocessed image + forensic context (ELA, EXIF, noise, FFT, etc.) +
   Sightengine API result
2. Runs the LLM with the `PRIMARY_INSTRUCTION` prompt (contains forensic reference ranges)
3. The LLM weighs all evidence: ELA anomalies, noise inconsistency, metadata red flags,
   Sightengine probabilities
4. Produces a final verdict (`real` / `fake` / `inconclusive`) with a confidence score

### supervisor_agent.py

1. Called from `runner.py` after Analysis Agent returns a verdict and the evidence
   sufficiency gate determines the case needs investigation
2. Receives an evidence table (verdicts from all consulted providers), forensic context
   (ELA, FFT, noise, DCT, wavelets, edge intensity, metadata), and the list of unused
   capabilities
3. Answers three questions in fixed order: what is unresolved, what evidence would help,
   does any untried capability provide it?
4. Outputs `{"action": "CONCLUDE"|"GET_SECOND_OPINION"|"INCONCLUSIVE_STOP", "capability": ..., "reasoning": ...}`
5. If GET_SECOND_OPINION, runner.py routes to the provider mapped to the requested
   capability and re-enters the evidence sufficiency gate for another round (max 2)

### report_agent.py

1. Receives the final verdict + all forensic evidence + agent reasoning
2. Generates a detailed narrative report in natural language
3. Optionally searches the web via Tavily for related news or known deepfake campaigns
4. Returns the structured report text ready for PDF generation
