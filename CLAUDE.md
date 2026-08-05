<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->

# ARKA — Asset Reliability Knowledge Agent

**EBCO AI Hackathon 2026 · Kategori B — AI Agent · Tema: Knowledge Management Solution · Solo**

Submission: **11 Agustus 2026** · Demo day: 14 Agustus · Pendaftaran: **7 Agustus**

---

## 🔒 Keputusan yang sudah terkunci — JANGAN dibuka ulang

Keputusan berikut sudah melalui pembahasan panjang dan **final**. Kalau ada keraguan,
baca `.context/hackathon-plan.md`, jangan memulai diskusi ulang. Waktu tersisa dipakai
untuk membangun, bukan memutuskan.

| Aspek | Keputusan |
|---|---|
| Nama | ARKA — Asset Reliability Knowledge Agent |
| Domain | Manufaktur FMCG **fiktif penuh** (minuman kemasan), 6–8 pabrik |
| Pembeda | Lapisan rantai pasok: **dynamic spare part criticality** |
| Pain point | Kegagalan sama berulang di pabrik berbeda, tiap kali dibayar dari nol |
| Framework agent | **Google ADK** — deploy ke Vertex AI Agent Engine |
| Database | PostgreSQL 16 + **Apache AGE** + pgvector |
| BigQuery Graph | ❌ Ditolak — GQL butuh reservation Enterprise; sandbox on-demand |
| Data | **Sintetis seluruhnya**, ditulis langsung ke tabel kanonik. **Tidak ada ETL** |
| Metode | Spec-Driven Development (GitHub Spec Kit) |

## 🚫 Batasan mutlak

1. **Tidak ada data klien.** Nol baris. Repo ini sengaja dibuat baru agar history-nya bersih.
2. **Jangan sebut nama perusahaan, sektor nyata, atau lokasi asli** di kode, komentar,
   maupun data. Domain disebut *"manufaktur FMCG multi-pabrik"* saja.
3. **Skema tag aset dirancang sendiri** — jangan meniru format sistem manapun.
4. **`.context/` tidak pernah di-commit** (berisi konteks komersial internal).
5. **Jangan pernah menyebut ARKA sebagai chatbot** — Kategori B menilai otonomi.
   Chat adalah antarmuka ke Investigator, bukan identitasnya.

## Arsitektur

```
Scout → Investigator → Reporter        (rantai)
Curator                                (ortogonal)
        ↓
PostgreSQL + Apache AGE + pgvector
        ↓
ADK Artifacts: memo · infografis · deck
```

### Empat agent — masing-masing punya satu keputusan

| Agent | Keputusan miliknya | Serah-terima |
|---|---|---|
| `scout` | Mana yang layak diselidiki | → investigator |
| `investigator` | Langkah penelusuran berikutnya; kapan eskalasi ke manusia | → reporter |
| `reporter` | Blok mana yang masuk dokumen dan urutannya | → artifact |
| `curator` | Pemetaan mana yang aman disetujui otomatis | → proyeksi ulang graph |

⚠️ **Jangan bangun framework.** Empat modul sederhana dengan kontrak jelas.

### Prinsip yang tidak boleh dilanggar

**Deterministik vs LLM** — fondasi kredibilitas seluruh sistem:

| Deterministik | LLM (Gemini) |
|---|---|
| Skor deteksi & kekritisan | Memutuskan jalur penelusuran berikutnya |
| Traversal graph | Menafsirkan teks bebas notifikasi |
| Angka, grafik, diagram, sitasi | Memilih blok dokumen, menyusun narasi |

**Model tidak pernah menyentuh angka.** Salah pilih blok tidak fatal; salah ketik angka fatal.

**Agent tidak pernah menulis fakta** ke graph — semua temuan masuk sebagai kandidat
`unreviewed` menunggu persetujuan manusia.

### Mekanisme deteksi (fondasi Babak 1 demo — harus bisa dijelaskan)

```
symptom_overlap  0,50   |gejala sekarang ∩ historis| / |historis|
component_match  0,20   1,0 komponen sama · 0,5 satu subsistem
corroboration    0,20   min(kasus serupa / 3, 1,0)
recency          0,10   peluruhan usia kasus

≥ 0,65 → laporkan · selisih dua kandidat ≤ 0,05 → eskalasi · < 0,50 → abaikan
```

### Criticality sparepart

```
criticality = 0,40·failure_probability + 0,35·consequence + 0,25·supply_risk
```
Nilai jualnya ada di **selisih terhadap `static_criticality`** di master data.

---

## Status & langkah berikutnya

**D0 selesai** — repo, Spec Kit, struktur ADK, kode dasar tersalin, compose.

**D1 (6 Agt):**
1. `uv sync` + `docker compose up -d`
2. `/speckit-specify` — kunci spesifikasi (sekalian bahan SDD, 8 poin)
3. Tulis ulang `app/synthetic/generator.py` sesuai spesifikasi data
4. Autogenerate migrasi awal dari models (`migrations/versions/` sengaja kosong)
5. Proyeksi graph — verifikasi preseden lintas pabrik keluar dari query

**D2 (7 Agt):** ⚠️ **DAFTARKAN PROJECT — deadline hari ini.** Scout + deteksi.
Investigator kerangka. **Uji deploy hello-world ke Agent Engine** (jangan tunda ke D5).

**D3:** Investigator penuh + jejak penalaran + sitasi · chat
**D4:** Memo + criticality + radius dampak — 🎯 **demo end-to-end harus jalan hari ini**
**D5:** Infografis · Curator · **rekam video** · bekukan fitur
**D6:** Submission

### Urutan pemotongan kalau tertinggal
1. PPTX → buang · 2. Curator → skrip batch sederhana · 3. Infografis → 3 blok saja

**Tidak pernah dipotong:** sitasi dokumen · jejak penalaran multi-hop · deploy Agent Engine

---

## Data sintetis — syarat jalur emas

| Kebutuhan | Detail |
|---|---|
| Armada seragam | Satu model filler di **≥5 pabrik** (kalau cuma 2, penemuannya sepele) |
| Pola berulang | 2×: kasus lama selesai + solusinya tercatat, kasus baru menguat |
| Rantai kausal | `Symptom → Cause → Damage → Part` penuh di kasus lama |
| Dokumen | 3–5 laporan inspeksi, memuat solusi yang berhasil, bisa dikutip |
| Kasus ambigu | Dua kandidat selisih ≤0,05 → memicu eskalasi |
| Rantai pasok | Sparepart vendor tunggal, lead time 6 minggu, dipakai ≥4 pabrik, `static_criticality` **rendah** |

Volume latar: ~5.000 equipment · ~20.000 work order · ~15.000 notifikasi · 2–3 tahun ·
katalog 200.000+ mapping yang **sengaja kotor** (typo ala OCR, tag ambigu, ~8% WO tanpa equipment).

---

## Referensi

| Dokumen | Isi |
|---|---|
| `.context/hackathon-plan.md` | Rencana lengkap, alasan tiap keputusan, rubrik, risiko |
| `.context/arka-pitch.md` | Naskah pitch per babak + persiapan Q&A |
| `docs/submission.md` | Dokumen untuk juri (aman dibagikan) |

## Konvensi

- Python 3.12 · `uv` · ruff line-length 100 · pytest asyncio auto
- Bahasa dokumen dan komentar: **Indonesia**
- `app/synthetic/` adalah alat waktu-pengembangan — tidak ikut ter-deploy ke Agent Engine
