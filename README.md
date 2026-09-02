# Summarizeeer

AI Document Summarizer — portofolio project.

## Status

- [x] **Tahap 1 — UI** (`frontend/index.html`): upload dropzone, validasi client-side, loading/result/error state.
- [x] **Tahap 2 — PDF → Text** (`backend/app/pdf_extractor.py`): backend FastAPI yang mengekstrak teks dari PDF (pypdf).
- [x] **Tahap 3 — Text → Summary** (`backend/app/summarizer.py`): teks hasil ekstraksi dikirim ke LLM API (Claude) dengan prompt terstruktur, hasilnya diparse jadi JSON (Executive Summary, Key Points, Main Findings, Conclusion) dan ditampilkan di frontend.
- [ ] Tahap 4 — Chunking untuk dokumen panjang (saat ini teks yang kepanjangan cuma dipotong + dikasih warning, belum di-chunk & digabung ulang)
- [ ] Tahap 5 — Output formatting lanjutan
- [ ] Tahap 6 — Error handling lanjutan
- [ ] Tahap 7 — Evaluasi manual

## Struktur

```
Summarizeeer/
├── frontend/
│   └── index.html          # UI, fetch ke backend /api/summarize
└── backend/
    ├── requirements.txt
    ├── .env.example         # contoh config (ANTHROPIC_API_KEY, dll)
    └── app/
        ├── main.py          # FastAPI app + endpoint /api/extract & /api/summarize
        ├── pdf_extractor.py # Tahap 2: PDF -> Text (pypdf)
        └── summarizer.py    # Tahap 3: Text -> Summary (Anthropic Claude API)
```

## Menjalankan backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # lalu isi ANTHROPIC_API_KEY di .env
uvicorn app.main:app --reload
```

Backend jalan di `http://127.0.0.1:8000`.

## Menjalankan frontend

Cukup buka `frontend/index.html` langsung di browser (double click, atau lewat Live Server di VSCode). `API_BASE` di dalam file itu sudah diset ke `http://127.0.0.1:8000` — ubah kalau backend dijalankan di alamat lain.

## Endpoint API

### `POST /api/summarize` (dipakai frontend, Tahap 3)

Menerima `multipart/form-data` dengan field `file` (PDF). Melakukan validasi + ekstraksi (Tahap 2) lalu meringkas hasilnya lewat LLM (Tahap 3) dalam satu panggilan.

Respons sukses (200):
```json
{
  "filename": "contoh.pdf",
  "page_count": 3,
  "total_chars": 408,
  "extraction_seconds": 0.02,
  "summarization_seconds": 2.1,
  "model": "claude-sonnet-5",
  "warnings": [],
  "summary": {
    "executive_summary": "...",
    "key_points": ["...", "..."],
    "main_findings": ["...", "..."],
    "conclusion": "..."
  }
}
```

Respons gagal (400/422/502/503) — pesan sudah aman ditampilkan ke user:
```json
{ "detail": "Unable to generate summary. Please try again." }
```

### `POST /api/extract` (Tahap 2, dipertahankan untuk debugging)

Endpoint lama yang hanya melakukan ekstraksi teks tanpa meringkas — berguna untuk mengecek hasil ekstraksi mentah tanpa memanggil (dan membayar) LLM API.

## Kondisi yang sudah ditangani

Dari Tahap 2:
- Bukan file PDF (cek content-type + ekstensi + signature `%PDF-`)
- Ukuran file > 10 MB (dicek ulang di server, tidak percaya validasi frontend)
- PDF kosong (0 halaman)
- PDF terkunci password
- PDF corrupt / tidak bisa dibaca
- PDF terindikasi hasil scan (rata-rata karakter per halaman terlalu rendah) → ditolak dengan pesan OCR belum didukung
- Dokumen sangat panjang (>300 halaman) → tetap diproses, tapi dikasih warning

Dari Tahap 3:
- `ANTHROPIC_API_KEY` belum diset di server → error jelas, bukan crash
- API LLM tidak bisa dihubungi / error → pesan aman, bukan stack trace
- Respons LLM gagal diparse sebagai JSON → ditangani, bukan bikin frontend rusak
- Teks yang terlalu panjang (> `MAX_SUMMARY_INPUT_CHARS`, default 60.000 karakter) → dipotong sementara + warning ke user, sambil menunggu chunking asli di Tahap 4

Belum ditangani (di luar cakupan v1 saat ini, sesuai roadmap): OCR untuk PDF scan, chunking dokumen panjang, ekstraksi tabel terstruktur, deteksi heading.
