"""PDF report generation service — converts markdown report to PDF."""

import os
import tempfile
from io import BytesIO
from pathlib import Path

from fpdf import FPDF

# ── Latin-1 character sanitization ──────────────────────────────────
# fpdf2's default Helvetica font only supports Latin-1 (ISO-8859-1).
# Characters outside this range (em-dash, smart quotes, ellipsis, etc.)
# crash with "Character outside the range of characters supported".
# This mapping replaces them with ASCII equivalents before PDF rendering.

_LATIN1_REPLACEMENTS: dict[str, str] = {
    "\u2013": "-",    # en-dash
    "\u2014": "--",   # em-dash
    "\u2015": "--",   # horizontal bar
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201a": ",",    # single low-9 quote
    "\u201b": "'",    # single high-reversed quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u201e": ",,",   # double low-9 quote
    "\u201f": '"',    # double high-reversed quote
    "\u2022": "*",    # bullet
    "\u2026": "...",  # ellipsis
    "\u2032": "'",    # prime
    "\u2033": '"',    # double prime
    "\u2212": "-",    # minus sign
    "\u2264": "<=",   # less-than or equal
    "\u2265": ">=",   # greater-than or equal
    "\u00a0": " ",    # non-breaking space
    "\uf0b7": "-",    # bullet (alt)
    "\uf020": " ",    # various Unicode private use area
}


def _sanitize_for_pdf(text: str) -> str:
    """Replace non-Latin-1 characters with ASCII equivalents."""
    for char, replacement in _LATIN1_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    # Encode to Latin-1, replacing any remaining out-of-range chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(markdown_text: str, output_path: str | None = None) -> bytes:
    """Generate a PDF document from markdown-style text.

    Args:
        markdown_text: Report text with markdown-style formatting.
        output_path: Optional file path to write the PDF. If None, returns bytes.

    Returns:
        PDF file as bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DeepGuard AI Forensic Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # Sanitize entire text before rendering (fpdf2 Helvetica = Latin-1 only)
    markdown_text = _sanitize_for_pdf(markdown_text)

    # Body
    pdf.set_font("Helvetica", size=11)

    for line in markdown_text.split("\n"):
        stripped = line.strip()

        if not stripped:
            pdf.ln(3)
        elif stripped.startswith("# ") or stripped.startswith("## "):
            level = 1 if stripped.startswith("# ") else 2
            pdf.set_font("Helvetica", "B", 14 if level == 1 else 12)
            pdf.cell(0, 8, stripped.lstrip("# ").strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=11)
        elif stripped.startswith("**") and stripped.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, stripped.strip("**"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=11)
        elif stripped.startswith("|"):
            continue
        else:
            pdf.cell(0, 6, stripped, new_x="LMARGIN", new_y="NEXT")

    if output_path:
        os.makedirs(Path(output_path).parent, exist_ok=True)
        pdf.output(output_path)
        return Path(output_path).read_bytes()

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
