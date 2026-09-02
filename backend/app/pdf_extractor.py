"""
pdf_extractor.py
-----------------
Tahap 2 — PDF -> Text.

Tanggung jawab modul ini HANYA satu: mengubah bytes PDF menjadi teks
yang bersih dan terstruktur per halaman, plus metadata yang berguna
untuk tahap berikutnya (chunking & summarization) dan untuk ditampilkan
di UI (jumlah halaman, waktu proses, dst).

Modul ini sengaja TIDAK menangani:
- OCR (PDF hasil scan / image-only) -> baru sebatas dideteksi & ditolak
- Upload / HTTP handling -> itu tugas main.py
- Summarization -> itu tahap 3
"""

from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFExtractionError(Exception):
    """
    Error terkontrol dengan pesan yang sudah aman ditampilkan ke user
    (bahasa Inggris, mengikuti gaya error di dokumen roadmap).
    Beda dengan exception mentah dari pypdf yang tidak boleh
    langsung diteruskan ke frontend.
    """
    def __init__(self, user_message: str, code: str):
        self.user_message = user_message
        self.code = code
        super().__init__(user_message)


@dataclass
class PageResult:
    page_number: int
    text: str
    char_count: int


@dataclass
class ExtractionResult:
    filename: str
    page_count: int
    pages: list[PageResult]
    full_text: str
    total_chars: int
    processing_seconds: float
    warnings: list[str] = field(default_factory=list)


# --- Batas & threshold untuk MVP (bisa dipindah ke config nanti) ---
MAX_PAGES = 300               # di atas ini, tetap diproses tapi dikasih warning
MIN_CHARS_PER_PAGE_AVG = 15   # di bawah ini => kemungkinan besar hasil scan/image


def _clean_text(raw: str) -> str:
    """
    Bersihkan artefak umum hasil ekstraksi PDF:
    - null byte & control character selain newline/tab
    - spasi berlebih
    - baris kosong berlebih (>2 jadi maksimal 2)
    """
    if not raw:
        return ""
    # buang null byte & control chars aneh, tapi pertahankan \n dan \t
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    # rapikan spasi ganda dalam satu baris
    raw = re.sub(r"[ \t]{2,}", " ", raw)
    # maksimal 2 baris kosong berturut-turut
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def extract_text(file_bytes: bytes, filename: str) -> ExtractionResult:
    """
    Ekstrak teks dari PDF (khusus PDF dengan selectable text — sesuai
    keputusan Step 2 di roadmap: OCR belum ditangani di v1).

    Melempar PDFExtractionError dengan pesan yang sudah siap tampil
    ke user untuk semua kondisi gagal yang sudah diantisipasi:
      - file corrupt / bukan PDF valid
      - PDF terkunci password
      - PDF kosong (0 halaman)
      - PDF terindikasi hasil scan (nyaris tidak ada selectable text)
    """
    start = time.perf_counter()

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise PDFExtractionError(
            "This file could not be read as a PDF. It may be corrupted.",
            code="corrupt_pdf",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - sengaja ditangkap luas, lalu disaring
        raise PDFExtractionError(
            "This file could not be read as a PDF. It may be corrupted.",
            code="corrupt_pdf",
        ) from exc

    if reader.is_encrypted:
        # Coba buka dengan password kosong (kadang PDF "encrypted" tapi tanpa password asli)
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            pass
        if reader.is_encrypted:
            raise PDFExtractionError(
                "This PDF is password-protected. Please upload an unlocked file.",
                code="encrypted_pdf",
            )

    page_count = len(reader.pages)
    if page_count == 0:
        raise PDFExtractionError(
            "This PDF appears to be empty.",
            code="empty_pdf",
        )

    warnings: list[str] = []
    if page_count > MAX_PAGES:
        warnings.append(
            f"This document has {page_count} pages, which is above the "
            f"recommended limit of {MAX_PAGES}. Processing may be slower."
        )

    pages: list[PageResult] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - satu halaman rusak jangan gagalkan semua
            raw_text = ""
        cleaned = _clean_text(raw_text)
        pages.append(PageResult(page_number=i, text=cleaned, char_count=len(cleaned)))

    total_chars = sum(p.char_count for p in pages)
    avg_chars_per_page = total_chars / page_count

    if avg_chars_per_page < MIN_CHARS_PER_PAGE_AVG:
        # Heuristik: nyaris tidak ada selectable text -> kemungkinan besar PDF hasil scan/image.
        raise PDFExtractionError(
            "This document appears to contain scanned images. "
            "OCR support is not available yet.",
            code="scanned_pdf",
        )

    full_text = "\n\n".join(p.text for p in pages if p.text)
    elapsed = time.perf_counter() - start

    return ExtractionResult(
        filename=filename,
        page_count=page_count,
        pages=pages,
        full_text=full_text,
        total_chars=total_chars,
        processing_seconds=round(elapsed, 2),
        warnings=warnings,
    )
