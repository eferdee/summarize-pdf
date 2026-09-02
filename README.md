# SummarizeePDF (Summarizeeer)

AI Document Summarizer — portofolio project.

Aplikasi web sederhana: user upload PDF, backend mengekstrak teksnya lalu meringkasnya jadi ringkasan terstruktur (Executive Summary, Key Points, Main Findings, Conclusion) lewat LLM. Untuk dokumen panjang, teks dipecah jadi beberapa bagian, diringkas per bagian, lalu digabung jadi satu ringkasan akhir.

## Cara kerja singkat

```
User upload PDF (frontend)
        │
        ▼
Validasi file (tipe, ukuran, signature %PDF-)
        │
        ▼
Ekstraksi teks per halaman (pypdf)
        │
        ▼
   teks pendek? ──yes──► satu kali panggilan LLM ──► JSON summary
        │no
        ▼
Split jadi beberapa chunk (per batas paragraf)
        │
        ▼
Ringkas tiap chunk (plain text, panggilan LLM terpisah)
        │
        ▼
Gabungkan semua ringkasan chunk → satu panggilan LLM terakhir
        │
        ▼
   JSON summary akhir → ditampilkan di frontend
```

## Teknologi yang digunakan

**Frontend** — statis, tanpa build step:
- HTML/CSS/vanilla JS (`frontend/`)
- Fetch API untuk komunikasi ke backend

**Backend** — `backend/`:
- [FastAPI](https://fastapi.tiangolo.com/) (Python) sebagai web framework
- [pypdf](https://pypdf.readthedocs.io/) untuk ekstraksi teks dari PDF
- [Google Gemini API](https://ai.google.dev/) (`google-genai` SDK) sebagai LLM untuk summarization — pakai `response_schema` supaya output dijamin JSON sesuai skema, bukan hasil parsing teks bebas
- `python-dotenv` untuk baca konfigurasi dari `.env`
- `uvicorn` sebagai ASGI server

> Catatan: versi awal proyek ini didesain untuk pakai Claude (Anthropic) sebagai LLM — kode & konfigurasi saat ini sudah pindah ke Gemini (`GEMINI_API_KEY`, model default `gemini-3.5-flash-lite`). README ini mengikuti implementasi yang aktif di kode.

## Fitur

- Upload PDF lewat dropzone (drag & drop atau klik) dengan validasi client-side
- Ekstraksi teks per halaman, dengan pembersihan artefak umum (spasi ganda, baris kosong berlebih, control character)
- Ringkasan terstruktur 4 bagian: Executive Summary, Key Points, Main Findings, Conclusion
- **Chunking otomatis** untuk dokumen panjang: teks dipecah per batas paragraf (bukan asal potong per-karakter), tiap bagian diringkas terpisah, lalu digabung jadi ringkasan akhir yang koheren
- Statistik hasil: jumlah halaman, jumlah karakter, jumlah chunk yang dipakai, waktu ekstraksi & summarization, jumlah kata hasil ringkasan
- Warning ke user untuk kondisi non-fatal (dokumen sangat panjang, teks terpotong, dsb) tanpa menggagalkan proses
- Pesan error yang aman ditampilkan ke user (tidak membocorkan stack trace / detail internal)

## Struktur

```
Summarizeeer/
├── frontend/
│   ├── index.html          # markup halaman, fetch ke backend /api/summarize
│   ├── css/
│   │   └── style.css       # semua styling
│   └── js/
│       ├── config.js       # API_BASE — ganti kalau backend jalan di alamat lain
│       ├── dom.js          # referensi elemen DOM + state, dipakai file JS lain
│       ├── render.js       # render hasil ringkasan dari backend ke DOM
│       ├── upload.js       # dropzone, validasi file, drag & drop
│       └── api.js          # panggilan fetch ke backend + state loading
└── backend/
    ├── requirements.txt
    ├── .env.example         # contoh config (GEMINI_API_KEY, dll)
    ├── test.py              # skrip uji manual
    └── app/
        ├── main.py          # FastAPI app + endpoint /api/extract & /api/summarize
        ├── pdf_extractor.py # PDF -> Text (pypdf)
        └── summarizer.py    # Text -> Summary + chunking (Gemini API)
```

## Cara menjalankan

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # lalu isi GEMINI_API_KEY di .env
uvicorn app.main:app --reload
```

Backend jalan di `http://127.0.0.1:8000`. Cek `GET /api/health` untuk memastikan server hidup.

Dapatkan API key gratis di [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Frontend

Cukup buka `frontend/index.html` langsung di browser (double click, atau lewat Live Server di VSCode) — tidak perlu langkah build apa pun. `API_BASE` di `frontend/js/config.js` sudah diset ke `http://127.0.0.1:8000`; ubah kalau backend dijalankan di alamat lain.

### Konfigurasi (`.env`)

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `GEMINI_API_KEY` | ya | — | API key Gemini |
| `SUMMARIZE_MODEL` | tidak | `gemini-3.5-flash-lite` | Model yang dipakai |
| `MAX_SUMMARY_INPUT_CHARS` | tidak | `240000` | Batas total karakter dokumen yang diproses; sisanya dipotong + warning |
| `SUMMARIZE_CHUNK_CHARS` | tidak | `12000` | Ukuran maksimal tiap chunk sebelum di-split |
| `SUMMARIZE_MAX_CHUNKS` | tidak | `20` | Batas jumlah chunk per dokumen |

## Endpoint API

### `POST /api/summarize` (dipakai frontend)

Menerima `multipart/form-data` dengan field `file` (PDF). Melakukan validasi + ekstraksi lalu meringkas hasilnya lewat LLM dalam satu panggilan (internal bisa berupa beberapa panggilan LLM kalau di-chunk).

Respons sukses (200):
```json
{
  "filename": "contoh.pdf",
  "page_count": 3,
  "total_chars": 408,
  "extraction_seconds": 0.02,
  "summarization_seconds": 2.1,
  "model": "gemini-3.5-flash-lite",
  "chunk_count": 1,
  "summary_word_count": 120,
  "warnings": [],
  "summary": {
    "executive_summary": "...",
    "key_points": ["...", "..."],
    "main_findings": ["...", "..."],
    "conclusion": "..."
  }
}
```

Respons gagal (400/422/429/502/503) — pesan sudah aman ditampilkan ke user:
```json
{ "detail": "Unable to generate summary. Please try again." }
```

### `POST /api/extract` (dipertahankan untuk debugging)

Endpoint lama yang hanya melakukan ekstraksi teks tanpa meringkas — berguna untuk mengecek hasil ekstraksi mentah tanpa memanggil (dan membayar kuota) LLM API.

### `GET /api/health`

Health check sederhana, `{ "status": "ok" }`.

## Kondisi yang sudah ditangani

**Ekstraksi PDF:**
- Bukan file PDF (cek content-type + ekstensi + signature `%PDF-`)
- Ukuran file > 10 MB (dicek ulang di server, tidak percaya validasi frontend)
- PDF kosong (0 halaman)
- PDF terkunci password
- PDF corrupt / tidak bisa dibaca
- PDF terindikasi hasil scan (rata-rata karakter per halaman terlalu rendah) → ditolak dengan pesan OCR belum didukung
- Dokumen sangat panjang (>300 halaman) → tetap diproses, tapi dikasih warning
- Satu halaman gagal diekstrak → tidak menggagalkan seluruh dokumen

**Summarization:**
- `GEMINI_API_KEY` belum diset di server → error jelas, bukan crash
- API key salah / tidak valid → pesan aman (503)
- Rate limit tercapai → pesan aman (429)
- Model tidak ditemukan / API LLM tidak bisa dihubungi → pesan aman (503/502)
- Respons LLM gagal diparse sebagai JSON → ditangani, bukan bikin frontend rusak
- Dokumen panjang → otomatis di-chunk per batas paragraf, diringkas bertahap, lalu digabung
- Teks yang tetap terlalu panjang setelah chunking (> `MAX_SUMMARY_INPUT_CHARS`) → dipotong + warning ke user

## Privasi & Data

**Di server aplikasi ini sendiri:** file PDF dan teks hasil ekstraksi hanya diproses di memory (`await file.read()` → `bytes` → diproses → dibuang setelah request selesai). Tidak ada penulisan ke disk, tidak ada database, tidak ada logging isi dokumen. Ini sudah diverifikasi langsung dari kode (`main.py`, `pdf_extractor.py`) — tidak ada satupun pemanggilan `open()`, `write()`, atau storage/database library di backend.

**Tapi teksnya tetap dikirim ke Google Gemini API (pihak ketiga)** untuk diringkas, dan kebijakan retensinya tergantung tier API key yang dipakai:

| | **API key tier gratis** (default di `.env.example`) | **API key tier berbayar** (billing aktif) |
|---|---|---|
| Dipakai untuk melatih model Google | **Ya** — teks yang dikirim boleh dipakai Google untuk improve produk/model mereka | Tidak |
| Direview manusia | Ya, memungkinkan | Tidak (kecuali untuk kasus abuse monitoring) |
| Retensi | Tidak didefinisikan eksplisit sebagai jangka pendek | ±55 hari, khusus untuk deteksi pelanggaran Prohibited Use Policy, lalu dihapus |

Sumber: [Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/docs/usage-policies) & [dokumentasi zero data retention Gemini API](https://ai.google.dev/gemini-api/docs/zdr) (Google AI for Developers, diakses September 2026).

**Implikasi praktis:** karena `.env.example` di project ini mengarah ke API key gratis (`aistudio.google.com/apikey`), secara default aplikasi ini **belum** dapat proteksi "tidak dipakai untuk training". Jangan upload dokumen yang sensitif/rahasia kecuali API key sudah diupgrade ke tier berbayar (enable billing di Google Cloud project). Disclaimer di UI ("Tidak disimpan di server kami") sudah diperbarui supaya tidak menyiratkan bahwa data 100% aman secara end-to-end — karena bagian yang berada di luar kendali kode ini (sisi Google) tidak bisa dijamin oleh aplikasi.

## Batasan (belum ditangani)

Di luar cakupan v1 saat ini:
- **OCR** — PDF hasil scan (gambar, bukan teks yang bisa diseleksi) tidak didukung, langsung ditolak dengan pesan error
- **Ekstraksi tabel terstruktur** — tabel ikut terbaca sebagai teks biasa, tidak dipertahankan strukturnya
- **Deteksi heading/struktur dokumen** — tidak ada pembedaan antara judul, sub-judul, dan isi; semua diperlakukan sebagai teks polos
- **Multi-file / batch upload** — hanya satu PDF per request
- **Autentikasi/multi-user** — tidak ada sistem login atau riwayat ringkasan per user
- **Bahasa** — ringkasan mengikuti bahasa dokumen asli (mengandalkan kemampuan model), tidak ada opsi terjemahan eksplisit
- Fidelity dijaga lewat prompt (dilarang menambah informasi/opini di luar teks sumber), tapi seperti LLM pada umumnya tetap ada kemungkinan kecil kesalahan — makanya ada disclaimer di UI ("bisa saja keliru — selalu cek ulang info penting")

## Roadmap

- [x] Tahap 1 — UI (upload dropzone, validasi client-side, loading/result/error state)
- [x] Tahap 2 — PDF → Text (FastAPI + pypdf)
- [x] Tahap 3 — Text → Summary (LLM, output JSON terstruktur)
- [x] Tahap 4 — Chunking untuk dokumen panjang
- [ ] Tahap 5 — Output formatting lanjutan
- [ ] Tahap 6 — Error handling lanjutan
- [ ] Tahap 7 — Evaluasi manual