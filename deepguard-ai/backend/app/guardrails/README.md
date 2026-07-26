# guardrails/

Safety checks that run before, during, and after processing. These make sure malicious
uploads are rejected, prompt injections are blocked, and agent responses are structurally
valid.

## Files

- **validation.py** — File-level validation: checks extension whitelist, path traversal
  attempts, file size limits, magic bytes, and ZIP bomb detection.
- **injection.py** — Text-level security: detects 30+ prompt injection patterns
  (role-play attacks, delimiter overrides, code execution requests) and redacts PII
  (file paths, emails, usernames).
- **schema.py** — JSON schema enforcement on LLM outputs. If an agent returns malformed
  JSON, it's caught here before reaching the caller.
- **moderation.py** — Content moderation: flags toxic, violent, or NSFW content in
  user inputs and agent outputs.

## Walkthrough

### validation.py + injection.py (the guard pipeline)

1. User uploads a file to the API
2. **Extension check** — reject if extension is `.exe`, `.zip`, `.scr`, etc.
3. **Path traversal check** — reject if filename contains `..` or `/` or `\0`
4. **File size check** — reject if file exceeds the configured limit (e.g. 20 MB)
5. **Magic bytes verification** — read the first bytes and compare against known
   signatures (JPEG, PNG, MP4, PDF, etc.)
6. **MIME type detection** — double-check the declared MIME type matches the magic bytes
7. **ZIP bomb detection** — if it's a compressed file, check compression ratio
8. **Injection detection** — run text inputs against the 30+ injection pattern list;
   redact or reject on match
9. **Schema validation** — after agents respond, validate their JSON output against
   the expected schema
