"""
summarizer.py

Tahap 3 -- Text -> Summary.
Tahap 4 -- Chunking untuk dokumen panjang.

Tanggung jawab modul ini:
mengubah teks hasil ekstraksi PDF menjadi ringkasan terstruktur
(Executive Summary, Key Points, Main Findings, Conclusion)
menggunakan Gemini API.

Alur untuk dokumen panjang (Tahap 4):

    Text
     |
    Split into chunks
     |
    Summarize each chunk (partial summary, plain text)
     |
    Combine partial summaries
     |
    Final structured summary (JSON schema)

Modul ini sengaja TIDAK menangani:
- Ekstraksi PDF -> pdf_extractor.py
"""

from __future__ import annotations

import json
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

# Batas total karakter yang MASIH diproses (sisanya dipotong + warning).
# Ini beda dari CHUNK_SIZE di bawah -- ini batas keseluruhan dokumen,
# bukan batas per-chunk.
MAX_INPUT_CHARS = int(
    os.environ.get("MAX_SUMMARY_INPUT_CHARS", "240000")
)

# Kalau teks sudah lebih pendek dari ini, tidak perlu di-chunk sama
# sekali -- langsung satu kali panggilan LLM (lebih cepat & murah).
CHUNK_SIZE_CHARS = int(
    os.environ.get("SUMMARIZE_CHUNK_CHARS", "12000")
)

# Batas jumlah chunk, supaya dokumen ekstrem panjang tidak menghasilkan
# ratusan panggilan API. MAX_INPUT_CHARS di atas otomatis membatasi ini
# juga, tapi kita jaga dua-duanya biar eksplisit.
MAX_CHUNKS = int(
    os.environ.get("SUMMARIZE_MAX_CHUNKS", "20")
)

MAX_OUTPUT_TOKENS = 1500
CHUNK_OUTPUT_TOKENS = 500


# =========================================================
# Prompt
# =========================================================

FIDELITY_RULES = """
Summarize ONLY what is present in the document text you are given.

Do not add information, opinions, assumptions, or facts that are not
present in the source text.

Copy dates, numbers, names, IDs, and other literal data EXACTLY as they
appear in the source text, character for character. Do not reformat,
reorder, translate, or "normalize" them (for example, do not swap
day/month order in dates, do not convert number formats, do not change
name order). If unsure of the exact format, quote it verbatim rather
than guessing.
"""

SYSTEM_PROMPT = f"""
You are a precise document summarization engine.

{FIDELITY_RULES}

If a section genuinely has nothing to report, return an empty list
or an empty string rather than inventing content.

The summary must be concise, factual, and faithful to the source.
"""

CHUNK_PROMPT = f"""
You are a precise document summarization engine helping summarize one
part of a longer document that has been split into several parts.

{FIDELITY_RULES}

Write a dense, factual plain-text summary of ONLY this part. Preserve
every important fact, figure, name, and date. Do not try to conclude
or summarize the whole document -- another step will combine all parts
later. Do not add headers, labels, or markdown formatting, just plain
prose.
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

    chunk_count: int = 1

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
# Chunking helpers
# =========================================================

def _split_into_chunks(text: str, chunk_size: int) -> list[str]:
    """
    Pecah teks jadi beberapa chunk sedapat mungkin di batas paragraf,
    supaya tidak memotong kalimat/tabel di tengah-tengah.

    Kalau ada satu paragraf yang sendirian sudah lebih panjang dari
    chunk_size (misal dokumen tanpa baris kosong sama sekali), paragraf
    itu dipotong paksa per-karakter.
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        # Fallback: dokumen tanpa "\n\n" sama sekali.
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:

        # Paragraf tunggal yang sudah kelewat panjang -> potong paksa.
        if len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), chunk_size):
                chunks.append(para[i:i + chunk_size])
            continue

        candidate = f"{current}\n\n{para}" if current else para

        if len(candidate) > chunk_size:
            chunks.append(current)
            current = para
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def _summarize_chunk(
    client: genai.Client,
    chunk_text: str,
    filename: str,
    index: int,
    total: int,
) -> str:

    prompt = (
        f"{CHUNK_PROMPT}\n\n"
        f"Document filename: {filename}\n"
        f"This is part {index + 1} of {total}.\n\n"
        "Part text:\n"
        "-----\n"
        f"{chunk_text}\n"
        "-----"
    )

    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=CHUNK_OUTPUT_TOKENS,
            ),
        )
    except Exception as exc:
        raise SummarizationError(
            "Unable to generate summary. Please try again.",
            code="api_error",
        ) from exc

    return (response.text or "").strip()


def _generate_structured_summary(
    client: genai.Client,
    input_text: str,
    filename: str,
    is_combined: bool = False,
) -> dict:
    """
    Panggilan terakhir yang menghasilkan JSON terstruktur
    (executive_summary, key_points, main_findings, conclusion).

    is_combined=True dipakai saat input_text adalah gabungan beberapa
    ringkasan chunk (bukan teks dokumen asli), supaya modelnya tahu
    tugasnya adalah menyatukan, bukan meringkas dari nol.
    """

    if is_combined:
        task_line = (
            "The text below is a set of partial summaries covering "
            "different parts of one longer document, in order. "
            "Combine them into a single coherent structured summary "
            "of the WHOLE document. Remove redundancy between parts, "
            "but keep it factual and faithful to what the parts say."
        )
    else:
        task_line = "Summarize the following document."

    user_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{task_line}\n\n"
        f"Document filename: {filename}\n\n"
        "Text:\n"
        "-----\n"
        f"{input_text}\n"
        "-----"
    )

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

    try:
        parsed = response.parsed
        if parsed is None:
            raise ValueError("Gemini returned no parsed JSON.")
    except Exception:
        try:
            parsed = json.loads(response.text)
        except Exception as exc:
            raise SummarizationError(
                "Unable to generate summary. Please try again.",
                code="bad_llm_output",
            ) from exc

    return parsed


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
    # Batas keseluruhan (jaga-jaga dokumen ekstrem panjang)
    # -----------------------------------------------------

    truncated = len(text) > MAX_INPUT_CHARS
    input_text = text[:MAX_INPUT_CHARS]

    if truncated:
        warnings.append(
            "This document is very long, so the summary is based on "
            f"roughly the first {MAX_INPUT_CHARS:,} characters only."
        )

    client = _get_client()

    # -----------------------------------------------------
    # Dokumen pendek -> tidak perlu chunking, langsung satu call
    # -----------------------------------------------------

    if len(input_text) <= CHUNK_SIZE_CHARS:
        parsed = _generate_structured_summary(
            client, input_text, filename, is_combined=False,
        )
        chunk_count = 1

    # -----------------------------------------------------
    # Dokumen panjang -> chunking (Tahap 4)
    # -----------------------------------------------------

    else:
        chunks = _split_into_chunks(input_text, CHUNK_SIZE_CHARS)

        if len(chunks) > MAX_CHUNKS:
            chunks = chunks[:MAX_CHUNKS]
            warnings.append(
                f"This document produced more than {MAX_CHUNKS} chunks; "
                "only the first portion was summarized."
            )

        chunk_count = len(chunks)

        chunk_summaries: list[str] = []
        for i, chunk in enumerate(chunks):
            partial = _summarize_chunk(
                client, chunk, filename, i, chunk_count,
            )
            if partial:
                chunk_summaries.append(f"[Part {i + 1}]\n{partial}")

        if not chunk_summaries:
            raise SummarizationError(
                "Unable to generate summary. Please try again.",
                code="bad_llm_output",
            )

        combined_text = "\n\n".join(chunk_summaries)

        warnings.append(
            f"This document was long, so it was split into {chunk_count} "
            "parts and summarized in stages before combining into the "
            "final summary."
        )

        parsed = _generate_structured_summary(
            client, combined_text, filename, is_combined=True,
        )

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
        chunk_count=chunk_count,
        warnings=warnings,
    )
