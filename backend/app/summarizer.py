"""
summarizer.py

Tahap 3 -- Text -> Summary.

Tanggung jawab modul ini:
mengubah teks hasil ekstraksi PDF menjadi ringkasan terstruktur
(Executive Summary, Key Points, Main Findings, Conclusion)
menggunakan Gemini API.

Modul ini sengaja TIDAK menangani:
- Chunking dokumen panjang -> Tahap 4
- Ekstraksi PDF -> pdf_extractor.py
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google import genai
from google.genai import types


# =========================================================
# Environment
# =========================================================

load_dotenv()


# =========================================================
# Konfigurasi
# =========================================================

DEFAULT_MODEL = os.environ.get(
    "SUMMARIZE_MODEL",
    "gemini-3.5-flash-lite"
)

MAX_INPUT_CHARS = int(
    os.environ.get("MAX_SUMMARY_INPUT_CHARS", "60000")
)

MAX_OUTPUT_TOKENS = 1500


# =========================================================
# Prompt
# =========================================================

SYSTEM_PROMPT = """
You are a precise document summarization engine.

Summarize ONLY what is present in the document text you are given.

Do not add information, opinions, assumptions, or facts that are not
present in the source text.

If a section genuinely has nothing to report, return an empty list
or an empty string rather than inventing content.

The summary must be concise, factual, and faithful to the source.
"""


# =========================================================
# Error
# =========================================================

class SummarizationError(Exception):
    """
    Error terkontrol dengan pesan yang aman ditampilkan ke user.
    """

    def __init__(self, user_message: str, code: str):
        self.user_message = user_message
        self.code = code
        super().__init__(user_message)


# =========================================================
# Result
# =========================================================

@dataclass
class SummaryResult:
    executive_summary: str
    key_points: list[str]
    main_findings: list[str]
    conclusion: str

    model: str
    input_chars_used: int
    truncated: bool
    processing_seconds: float

    warnings: list[str] = field(default_factory=list)


# =========================================================
# Gemini Client
# =========================================================

def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise SummarizationError(
            "Summarization is not configured on the server yet "
            "(missing API key).",
            code="missing_api_key",
        )

    return genai.Client(api_key=api_key)


# =========================================================
# Summary Schema
# =========================================================

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "2-4 sentence overview of the whole document.",
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "Important points from the document.",
        },
        "main_findings": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "description": "Main findings or significant information.",
        },
        "conclusion": {
            "type": "string",
            "description": "1-3 sentence conclusion or takeaway.",
        },
    },
    "required": [
        "executive_summary",
        "key_points",
        "main_findings",
        "conclusion",
    ],
}


# =========================================================
# Main Function
# =========================================================

def summarize_text(
    text: str,
    filename: str = "document.pdf",
) -> SummaryResult:

    if not text or not text.strip():
        raise SummarizationError(
            "There is no extracted text to summarize.",
            code="empty_text",
        )

    start = time.perf_counter()

    warnings: list[str] = []

    # -----------------------------------------------------
    # Temporary limitation for long documents
    # -----------------------------------------------------

    truncated = len(text) > MAX_INPUT_CHARS

    input_text = text[:MAX_INPUT_CHARS]

    if truncated:
        warnings.append(
            "This document is long, so the summary is based on "
            f"roughly the first {MAX_INPUT_CHARS:,} characters only. "
            "Full-document chunking is coming in a later version."
        )

    # -----------------------------------------------------
    # Client
    # -----------------------------------------------------

    client = _get_client()

    # -----------------------------------------------------
    # Prompt
    # -----------------------------------------------------

    user_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Summarize the following document.\n\n"
        f"Document filename: {filename}\n\n"
        "Document text:\n"
        "-----\n"
        f"{input_text}\n"
        "-----"
    )

    # -----------------------------------------------------
    # Gemini request
    # -----------------------------------------------------

    try:

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_OUTPUT_TOKENS,

                response_mime_type="application/json",

                response_schema=SUMMARY_SCHEMA,
            ),
        )

    except Exception as exc:

        raise SummarizationError(
            "Unable to generate summary. Please try again.",
            code="api_error",
        ) from exc

    # -----------------------------------------------------
    # Parse response
    # -----------------------------------------------------

    try:

        parsed = response.parsed

        if parsed is None:
            raise ValueError("Gemini returned no parsed JSON.")

    except Exception:

        # Fallback jika SDK tidak menyediakan parsed
        try:
            import json

            parsed = json.loads(response.text)

        except Exception as exc:

            raise SummarizationError(
                "Unable to generate summary. Please try again.",
                code="bad_llm_output",
            ) from exc

    # -----------------------------------------------------
    # Extract fields
    # -----------------------------------------------------

    executive_summary = str(
        parsed.get("executive_summary", "") or ""
    ).strip()

    key_points = [
        str(point).strip()
        for point in parsed.get("key_points", [])
        if str(point).strip()
    ]

    main_findings = [
        str(point).strip()
        for point in parsed.get("main_findings", [])
        if str(point).strip()
    ]

    conclusion = str(
        parsed.get("conclusion", "") or ""
    ).strip()

    # -----------------------------------------------------
    # Processing time
    # -----------------------------------------------------

    elapsed = time.perf_counter() - start

    return SummaryResult(
        executive_summary=executive_summary,
        key_points=key_points,
        main_findings=main_findings,
        conclusion=conclusion,
        model=DEFAULT_MODEL,
        input_chars_used=len(input_text),
        truncated=truncated,
        processing_seconds=round(elapsed, 2),
        warnings=warnings,
    )