# services/

Output-formatting code that turns the analysis verdict and evidence into deliverable
documents. These are the final step — what the end-user actually sees or downloads.

## Files

- **report_service.py** — `build_report_json()` assembles the verdict, evidence, and
  reasoning into a structured JSON object. `format_report_markdown()` converts that JSON
  into a readable markdown string for the user.
- **pdf_service.py** — Generates a downloadable PDF from the markdown report using
  fpdf2. Handles character encoding issues with Latin-1 sanitization so the PDF renders
  cleanly in any viewer.
- **audit_service.py** — Tamper-resistant audit log. Every analysis is recorded with
  SHA-256 hashes chained across entries (each entry's hash includes the previous hash).
  HMAC authentication prevents log forgery.

## Walkthroughs

### pdf_service.py

1. Receives the markdown report text from `report_service.format_report_markdown()`
2. Parses markdown headings, paragraphs, and bullet points and converts them to PDF
   pages with fpdf2
3. Maps all characters to Latin-1 safe equivalents so no encoding errors occur during
   PDF rendering
4. Returns the raw PDF bytes ready for download
