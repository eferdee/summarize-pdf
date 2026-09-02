"""
main.py
-------
Backend Summarizeeer.

Endpoint:
- POST /api/extract     -> Tahap 2: PDF -> Text saja (dipertahankan untuk debugging)
- POST /api/summarize    -> Tahap 3: PDF -> Text -> Summary (LLM), ini yang dipakai frontend

Belum ada di sini (menyusul di Tahap 4):
- chunking untuk dokumen panjang (saat ini teks panjang cuma dipotong + warning)
"""

from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.pdf_extractor import extract_text, PDFExtractionError, ExtractionResult
from app.summarizer import summarize_text, SummarizationError

try:
    # Opsional: kalau python-dotenv terinstall, baca .env otomatis supaya
    # ANTHROPIC_API_KEY tidak perlu diset manual tiap buka terminal baru.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

app = FastAPI(title="Summarizeeer API", version="0.3.0")

# Untuk MVP: izinkan semua origin (frontend masih file statis / localhost).
# Persempit ini kalau nanti sudah deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


async def _validate_and_extract(file: UploadFile) -> ExtractionResult:
    """
    Validasi file + ekstraksi teks. Dipakai bersama oleh /api/extract dan
    /api/summarize supaya logikanya tidak duplikat.
    """
    # --- Validasi 1: tipe file ---
    is_pdf_mime = file.content_type == "application/pdf"
    is_pdf_ext = (file.filename or "").lower().endswith(".pdf")
    if not (is_pdf_mime or is_pdf_ext):
        raise HTTPException(status_code=400, detail="Please upload a PDF document.")

    content = await file.read()

    # --- Validasi 2: ukuran file ---
    # Frontend sudah cek ini juga, tapi backend TIDAK BOLEH percaya
    # validasi client-side saja.
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size must be below {MAX_FILE_SIZE_MB} MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="This document appears to be empty.")

    # --- Validasi 3: signature PDF (%PDF-) ---
    if not content.lstrip()[:5].startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Please upload a PDF document.")

    # --- Ekstraksi ---
    try:
        return extract_text(content, filename=file.filename or "document.pdf")
    except PDFExtractionError as exc:
        raise HTTPException(status_code=422, detail=exc.user_message) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="Unable to process file. Please try again.",
        ) from exc


def _extraction_to_dict(result: ExtractionResult) -> dict:
    return {
        "filename": result.filename,
        "page_count": result.page_count,
        "total_chars": result.total_chars,
        "processing_seconds": result.processing_seconds,
        "warnings": result.warnings,
        "pages": [
            {"page_number": p.page_number, "char_count": p.char_count, "text": p.text}
            for p in result.pages
        ],
        "full_text": result.full_text,
    }


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    result = await _validate_and_extract(file)
    return JSONResponse(_extraction_to_dict(result))


@app.post("/api/summarize")
async def summarize(file: UploadFile = File(...)):
    extraction = await _validate_and_extract(file)

    try:
        summary = summarize_text(extraction.full_text, filename=extraction.filename)
    except SummarizationError as exc:
        # 503 kalau masalahnya konfigurasi/koneksi server, 502 kalau LLM-nya
        # sendiri yang bermasalah (error / output aneh).
        status = 503 if exc.code in ("missing_api_key", "connection_error") else 502
        raise HTTPException(status_code=status, detail=exc.user_message) from exc
    except Exception as exc:  # noqa: BLE001
        # Error tak terduga -> JANGAN bocorkan detail internal ke user.
        raise HTTPException(
            status_code=500,
            detail="Unable to generate summary. Please try again.",
        ) from exc

    combined_warnings = list(extraction.warnings) + list(summary.warnings)

    return JSONResponse(
        {
            "filename": extraction.filename,
            "page_count": extraction.page_count,
            "total_chars": extraction.total_chars,
            "extraction_seconds": extraction.processing_seconds,
            "summarization_seconds": summary.processing_seconds,
            "model": summary.model,
            "warnings": combined_warnings,
            "summary": {
                "executive_summary": summary.executive_summary,
                "key_points": summary.key_points,
                "main_findings": summary.main_findings,
                "conclusion": summary.conclusion,
            },
        }
    )
