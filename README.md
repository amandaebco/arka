# ARKA — Asset Reliability Knowledge Agent

> Agent otonom yang menyingkap akar masalah keandalan mesin, dengan bukti yang bisa ditelusuri.

**EBCO AI Hackathon 2026 · Kategori B — AI Agent · Tema: Knowledge Management Solution**

---

## Status

✅ **Siap untuk Submission & Penjurian EBCO AI Hackathon 2026.**

## Ringkasan

ARKA menyelidiki akar masalah kegagalan mesin di manufaktur multi-pabrik. Berjalan di atas
knowledge graph, ia menelusuri hubungan antara aset, riwayat perbaikan, dokumen inspeksi, dan
rantai pasok sparepart — untuk menemukan penyebab yang tidak terlihat di sistem manapun, lalu
menyusunnya menjadi dokumen yang setiap klaimnya bisa ditelusuri ke sumber aslinya.

## Arsitektur

```
        ┌──────────────────────────────────────────────┐
        │              Google ADK                      │
        │  Scout → Investigator → Reporter → Designer  │
        │  Penilai + Penilai Visual (gerbang mutu)     │
        │  Curator (ortogonal)                         │
        └───────────────────┬──────────────────────────┘
                            │
        ┌───────────────────┴──────────────────────────┐
        │   BigQuery — 39 tabel kanonik (sumber)       │
        │   graph_nodes / graph_edges · VECTOR_SEARCH  │
        │   lokal: PostgreSQL 16 + Apache AGE          │
        └───────────────────┬──────────────────────────┘
                            │
        ┌───────────────────┴──────────────────────────┐
        │  ADK Artifacts: memo · infografis · deck     │
        └──────────────────────────────────────────────┘
```

## Menjalankan & Penjurian

### 🚀 One-Command Bootstrap (Sangat Direkomendasikan)
Untuk kemudahan pengujian dan penjurian, jalankan skrip bootstrap otomatis berikut:

```bash
bash scripts/bootstrap.sh
```
Skrip ini secara otomatis melakukan pengecekan dependensi, konfigurasi `.env`, inisialisasi kontainer PostgreSQL (Apache AGE + pgvector), migrasi skema database, dan pembentukan dataset sintetis dalam satu langkah.

### Jalur Manual
```bash
cp .env.example .env                       # isi kredensial
uv sync                                    # dependensi
docker compose up -d                       # PostgreSQL (tempat generator menulis)
uv run alembic upgrade head                # skema

uv run python -m app.synthetic.generator --reset --volume-latar
uv run python scripts/migrasi_bigquery.py --full    # salin → verifikasi → indeks

uv run python scripts/run_chain.py         # scout → investigator → reporter
uv run python scripts/pindai_terjadwal.py  # pemindaian, tanpa model
```

Sumber data bawaannya **BigQuery** (`ARKA_STORE=postgres` untuk memaksa jalur lokal).
Kedua titik masuk menolak jalan bila salinan BigQuery tidak sepadan dengan PostgreSQL.

## Fitur Kunci & Pemenuhan Kriteria Submission

1. **GraphRAG & BigQuery Knowledge Graph**: Mengintegrasikan 39 tabel kanonik BigQuery dengan tabel `graph_nodes` dan `graph_edges` untuk eksekusi query relasional dan graf terpadu.
2. **VectorDB Retrieval**: Menggunakan `pgvector` di PostgreSQL lokal dan `VECTOR_SEARCH` di BigQuery untuk pencarian semantik berkinerja tinggi.
3. **Korpus Dokumen Sintetis**: Menghasilkan **50 dokumen latar inspeksi teknis** terstruktur (`app/synthetic/dokumen_latar.py`).
4. **Penelusuran Graf Multi-Hop**: Mendukung pencarian berantai **4 hingga 5 hop** dari *Asset $\rightarrow$ Work Order $\rightarrow$ Notification $\rightarrow$ SparePart $\rightarrow$ Plant Lain*.
5. **Cakupan Skenario Kasus**:
   - **Reliability Case**: Investigasi akar masalah keandalan mesin, analisis riwayat perbaikan, FMEA, dan catatan teknisi.
   - **Supply Chain Case**: Pelacakan batch sparepart terdistribusi (*batch tracking*) untuk mendeteksi cacat vendor lintas pabrik (`specs/006-batch-sparepart-tracking`).
6. **Multi-Tier Caching Layer & Performance Optimization**: Modul caching terpusat (`app/core/cache.py`) berbasis TTL yang menghemat panggilan database dan konsumsi token LLM.

## Infografis

Designer menerbitkan satu halaman infografis dari temuan yang sudah diselesaikan Reporter.
Ia tidak memilih isi: urutan blok datang dari Reporter lewat state sesi, dan seluruh teks
kanvas disusun verbatim dari `Finding`. Yang ditentukan Designer hanya penyajiannya — gaya,
penekanan, dan bentuk.

Dua persona tersedia: `engineer` (diagnosis teknis) dan `reliability_manager` (bawaan,
ringkas untuk keputusan).

```bash
uv run python scripts/render_infografis.py --persona engineer   # gambar satu halaman
uv run python scripts/render_infografis.py --prompt-saja        # lihat prompt, tanpa biaya
uv run python scripts/jalankan_penerbitan.py                    # rantai penuh, sesi ADK hidup
uv run python scripts/jalankan_penerbitan.py --hanya-designer   # lewati Reporter
```

Menggambar butuh `IMAGE_API_KEY`; pemeriksaan halaman butuh `GOOGLE_CLOUD_PROJECT`.

**Gerbang mutu.** Konstitusi mengecualikan tahap menggambar dari Prinsip I, dengan tiga
imbangan — dan yang menegakkannya di sini adalah pemeriksaan berbasis vision: Gemini
mentranskripsi halaman yang sudah jadi, lalu kode memutuskan teks mana yang berwenang tampil
(`app/designer/inspection.py`). Pemeriksaan yang tidak berjalan diperlakukan sebagai gagal,
bukan lulus.

Vonisnya dibedakan dua tingkat, karena dua hal berbeda pernah diperlakukan sama beratnya.
**Karangan** — teks yang tidak punya padanan di isi kanvas, seperti chip "Lokasi Fungsional"
yang diangkat dari judul dokumen — memblokir penerbitan. **Cacat cetak** — teks berwenang
yang salah eja, seperti "Catatan Teknis" untuk "Catatan Teknisi" — dilaporkan dan tercatat di
jejak, tapi tidak memblokir: menggambar ulang tidak dapat diandalkan memperbaiki satu huruf,
dan dua run pernah menghabiskan seluruh jatah tiga putaran karenanya. Toleransinya sempit
(≥ 12 karakter, kemiripan ≥ 0,9), sehingga kata pendek seperti "Sedang" tetap dihitung karangan.

**Bentuk kartu mengikuti data, bukan nama blok.** `app/designer/forms.py` menyaring 17 pola
visualisasi terhadap isi tiap kartu — berapa butir, mana yang punya angka sungguhan, tanggal,
atau tingkat — lalu designer memilih dari yang tersisa. Kartu yang tidak punya tanggal tidak
akan pernah ditawari linimasa, sehingga halaman tidak perlu mengarang stempel waktu untuk
mengisinya.

**Jejak audit.** Satu folder per penerbitan di `out/infografis/<stempel>-<temuan>/`, berisi
temuan, isi kanvas, spesifikasi, prompt, halaman, dan hasil tiap putaran. Karena gambar tidak
bisa direproduksi byte demi byte, jejak inilah catatannya. Bila `ARTIFACT_GCS_BUCKET` disetel,
jejak dicerminkan ke GCS agar tidak ikut hilang bersama instance Cloud Run.

## Data

**Seluruh data dibangkitkan secara sintetis.** Tidak ada data nyata milik pihak manapun.

## Rencana Pengembangan & Improvement Masa Depan

1. **IoT / SCADA Telemetry Streaming (Real-time Prescriptive Alert)**: Menghubungkan ARKA ke aliran data sensor IoT via Google Cloud Pub/Sub untuk memicu pemindaian otomatis sebelum kegagalan mesin terjadi.
2. **Multi-Modal Technical Drawing Parsing**: Menggunakan kemampuan penglihatan Gemini untuk membaca diagram P&ID, skematik CAD, dan citra termal untuk diekstrak secara otomatis menjadi struktur graf.
3. **Human-in-the-Loop (HITL) Active Learning**: Menyediakan antarmuka konfirmasi bagi chief reliability engineer untuk memverifikasi temuan agent, di mana feedback dituliskan kembali ke Knowledge Graph (`VERIFIED_BY_ENGINEER`).
4. **Direct Connectors untuk SAP PM & IBM Maximo**: Menyediakan konektor native zero-ETL untuk otomatisasi sinkronisasi data dari sistem ERP/CMMS industri.
5. **Closed-Loop Execution**: Memungkinkan ARKA untuk membuat draft Work Order otomatis di SAP atau memesan alokasi batch sparepart setelah laporan disetujui manajemen.

## Pengembangan

Proyek ini memakai **Spec-Driven Development** ([GitHub Spec Kit](https://github.com/github/spec-kit)).
Spesifikasi ada di `.specify/` dan `specs/`; alurnya `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

```bash
uv run pytest
uv run ruff check .
```
