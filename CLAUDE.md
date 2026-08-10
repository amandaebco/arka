<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/001-arka-knowledge-agent/plan.md`
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
| BigQuery Graph | ⚠️ **Direvisi 11 Agt** — lihat catatan di bawah |
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
Scout → Investigator → Reporter → Designer   (rantai)
Curator                                      (ortogonal)
        ↓
PostgreSQL + Apache AGE + pgvector
        ↓
ADK Artifacts: memo · infografis · deck
```

### Lima agent — masing-masing punya satu keputusan

| Agent | Keputusan miliknya | Serah-terima |
|---|---|---|
| `scout` | Mana yang layak diselidiki | → investigator |
| `investigator` | Langkah penelusuran berikutnya; kapan eskalasi ke manusia | → reporter |
| `reporter` | Blok mana yang masuk dokumen dan urutannya | → designer, artifact |
| `designer` | Penekanan visual dan bentuk visual tiap blok | → artifact |
| `curator` | Pemetaan mana yang aman disetujui otomatis | → proyeksi ulang graph |

Batas `reporter` ↔ `designer` dijaga ketat: pemilihan blok tetap milik reporter,
designer menerimanya sebagai masukan. Dua agent tidak boleh punya keputusan sama.

⚠️ **Jangan bangun framework.** Lima modul sederhana dengan kontrak jelas.

### Prinsip yang tidak boleh dilanggar

**Deterministik vs LLM** — fondasi kredibilitas seluruh sistem:

| Deterministik | LLM (Gemini) |
|---|---|
| Skor deteksi & kekritisan | Memutuskan jalur penelusuran berikutnya |
| Traversal graph | Menafsirkan teks bebas notifikasi |
| Angka, grafik, diagram, sitasi | Memilih blok dokumen, menyusun narasi |
| Penyusunan nilai untuk seluruh keluaran | Mengusulkan penekanan & bentuk visual |

**Model tidak pernah menyentuh angka.** Salah pilih blok tidak fatal; salah ketik angka fatal.

**Cakupan (Constitution 1.2.0).** Prinsip ini mengikat penuh pada **dokumen bukti**
— memo, nota dinas, laporan. **Infografis dikecualikan pada tahap penggambaran**
saja: teks dan angkanya tetap disusun kode dari `Finding`, yang berasal dari model
hanya penggambaran halaman. Tiga imbangan wajib menyertainya:

1. Tidak ada nilai yang hanya dibawa bentuk — setiap angka juga tertulis
2. Penilai memeriksa setiap string terhadap `Finding` sebelum terbit
3. Memo tetap catatan resmi untuk angka yang dipakai mengambil keputusan

Yang dipertaruhkan pada infografis adalah keterbacaan; pada memo, kebenaran.
Keduanya tidak ditukar.

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

**D1 (6 Agt) — sebagian selesai.** Project **sudah didaftarkan**.

Selesai:
- ✅ Constitution diisi (`.specify/memory/constitution.md`) — 6 prinsip, v1.0.0
- ✅ Spec 001 diisi — 5 user story, 20 FR, 7 SC, tabel status brownfield
- ✅ **Lapisan pelaporan penuh** — dikerjakan mendahului jadwal (materi D4)
- ✅ Reporter diuji hidup ke Gemini: `ringkas_temuan` → `muat_temuan` →
  `terbitkan_dokumen` → artifact PDF tersimpan, tanpa campur tangan
- ✅ Agent hello-world (`app/agents/hello.py`) jalan lokal via Vertex AI

Berlanjut di D2 — status terbaru:
- ✅ `uv sync` + `docker compose up -d` — AGE + pgvector aktif
- ✅ Migrasi awal + atribut rantai pasok pada `spare_parts` (40 tabel)
- ✅ `app/synthetic/generator.py` ditulis ulang — langsung ke tabel kanonik, tanpa CSV.
  Syarat jalur emas jadi konstanta di `app/synthetic/jalur_emas.py`
- ✅ Preseden lintas pabrik terbukti keluar dari query SQL
- ⬜ **Kalibrasi kasus ambigu ≤0,05** — sengaja ditunda sampai scorer Scout ada,
  supaya diukur, bukan ditebak
- ⬜ Volume latar (~5.000 equipment, ~20.000 WO) di atas jalur emas
- ⬜ `app/synthetic/validation.py` sebagai penjaga — versi lama (bentuk CSV) dihapus
- ⬜ Proyeksi graph — `app/graph/project.py` sudah ada, belum dijalankan

**D2–D4 — rantai deteksi selesai (10 Agt).**

`Scout → Investigator → Reporter` **hidup end-to-end**. Tidak ada manusia yang
menyebut kasusnya: scout memindai armada, investigator menelusuri, reporter
menerbitkan PDF. 217 tes hijau.

| Modul baru | Peran |
|---|---|
| `app/detection/scoring.py` | Empat komponen skor, ambang, `decide()` — nol model |
| `app/detection/repository.py` | Query read-only atas tabel kanonik |
| `app/detection/criticality.py` | Kekritisan dinamis sparepart |
| `app/detection/investigation.py` | Merakit `Finding`, menyaring kasus untuk scout |
| `app/agents/investigator.py` | Memutuskan kasus mana dan sedalam apa |
| `app/agents/scout.py` | Memutuskan apa yang layak diselidiki |
| `adk_agents/arka/` | Rantai penuh sebagai satu titik masuk tersaji |

**Angka hasil pengukuran 10 Agt — jangan diturunkan ulang, ini fakta tentang data:**

```
PLT-U/FIL-207 (Pabrik Utara) — kasus hidup
  PNY-SEAL-DEGRADASI    0,9073   Barat, Timur          komponen sama
  PNY-TORSI-MENYIMPANG  0,8821   Barat, Selatan, Tengah  subsistem sama
  margin 0,0252 → ESKALASI

PLT-G/FIL-412  0,7406 → laporkan
PLT-S/FIL-118  0,2821 → diabaikan (di bawah ambang 0,50)

Sparepart seal: ARKA 0,8667 vs master data 0,30 → selisih 0,5667
```

Kalibrasi eskalasi butuh preseden torsi ketiga — dengan dua, marginnya 0,0919 dan
eskalasi tidak pernah terpicu. **Yang disetel datanya; bobot dan ambang tidak
pernah disentuh**, karena keduanya kebijakan yang diterbitkan.

⚠️ Kasus `kasus-sepele-selatan` di `jalur_emas.py` **sengaja ada untuk diabaikan**.
Jangan dihapus: tanpa satu pun kasus yang ditolak, penyaring Scout tidak bisa
dibantah, dan tes `test_something_is_actually_ignored` akan merah.

**Belum:** deploy ulang ke Cloud Run (image masih versi 7 Agt, belum memuat
scout/investigator), `curator`, volume latar, proyeksi graph.

### BigQuery Graph — keputusan lama direvisi (11 Agt)

Penolakan semula ("GQL butuh reservation Enterprise") **benar separuh**. Diuji
langsung di `ebco-aihack-amanda`, on-demand, tanpa reservation:

| | On-demand |
|---|---|
| `CREATE PROPERTY GRAPH` | ✅ berhasil |
| `GRAPH_EXPAND(...)` — traversal lewat SQL | ✅ **berhasil** |
| `GRAPH … MATCH …` — sintaks GQL penuh | ❌ menuntut Enterprise |

Jadi yang berbayar adalah **sintaks GQL**, bukan kemampuan menelusuri graph.
`scripts/uji_bigquery_graph.py` memuat jalur emas ke BigQuery, membangun property
graph, lalu menemukan preseden lintas pabrik dengan **angka overlap identik**
dengan rantai lokal (1,0000 dan 0,6667).

Konsekuensinya untuk produksi: jalur BigQuery **tidak terhalang lisensi**. Yang
perlu ditulis ulang hanya `app/detection/repository.py` — satu-satunya berkas
yang menyentuh penyimpanan; semua di atasnya bekerja pada dataclass.

Hackathon tetap memakai PostgreSQL + AGE: sudah terbukti, dan memindahkannya di
hari submission bukan risiko yang sepadan.

### Dua penyimpanan, satu lapisan penalaran (11 Agt)

`ARKA_STORE` memilih backend; bawaannya `postgres`. Nilai tak dikenal jatuh ke
PostgreSQL, **bukan** ke cloud — salah ketik tidak boleh diam-diam memindahkan
sumber data produksi.

```bash
python scripts/run_chain.py                       # PostgreSQL + AGE
ARKA_STORE=bigquery python scripts/run_chain.py   # BigQuery property graph
```

**Paritas terukur, bukan diklaim:** rantai yang sama atas data yang sama
menghasilkan `0.9071` / `0.8819`, eskalasi pada margin `0.0252`, 5 preseden,
4 sitasi — identik dari kedua penyimpanan.

Yang **bisa** dialihkan: scout, investigator, `scripts/pindai_terjadwal.py`.
Yang **selalu BigQuery**: GraphRAG, `VECTOR_SEARCH`, agent tanya-jawab — embedding
hanya ada di sana.
Yang **selalu PostgreSQL**: generator sintetis (sumber kebenaran) dan tes.

⚠️ **Data BigQuery adalah salinan**, diisi `scripts/uji_bigquery_graph.py` dari
PostgreSQL. Kalau jalur emas berubah dan sinkronisasi tidak dijalankan, salinan
itu basi tanpa peringatan — mode kegagalan yang sama yang dulu membuat kita
memilih tabel kanonik ketimbang proyeksi AGE. Di produksi, BigQuery jadi sumber
langsung dan langkah ini hilang.

### Lapisan retrieval — GraphRAG dan tanya-jawab (11 Agt)

| Modul | Peran |
|---|---|
| `app/retrieval/embedding.py` | Embedding `gemini-embedding-001`, 3072 dimensi |
| `app/retrieval/vector_store.py` | `VECTOR_SEARCH` di BigQuery |
| `app/retrieval/graphrag.py` | Menggabungkan traversal graph + potongan dokumen |
| `app/agents/tanya_jawab.py` | `retriever` (apa yang diambil) + `answerer` (apa yang didukung bukti) |

**Embedding dibuat di luar BigQuery**, bukan lewat `ML.GENERATE_EMBEDDING`: fungsi
itu menuntut koneksi remote model yang service account-nya harus diberi akses
Vertex, dan akun ini tidak boleh `setIamPolicy`. `VECTOR_SEARCH` sendiri tidak
butuh koneksi apa pun.

⚠️ **Ambang kemiripan 0,60 adalah properti korpus, bukan properti model.** Diukur
atas empat dokumen: pertanyaan dalam kata-kata berbeda mencapai 0,61–0,72,
pertanyaan di luar domain masih 0,56. **Wajib diukur ulang** begitu dokumennya
banyak.

### Deploy Agent Engine — sudah terbukti jalan (7 Agt)

Project pindah ke **`ebco-aihack-amanda`** (peran `editor`, jadi bisa bikin bucket).
Staging bucket: `gs://ebco-aihack-amanda-arka-staging`. Resep tersimpan di
`scripts/deploy_hello.py` (jalur pickle) dan `scripts/deploy_sumber.py` (jalur sumber).

Yang terbukti:
- ✅ Agent ter-deploy hidup, menjawab, dan memanggil tool
- ✅ Model `gemini-3.6-flash` di lokasi **`global`** bisa dipanggil dari agent di
  region `us-central1` — jangan pindahkan model ke region, ia memang tidak ada di sana

Jebakan yang mahal ditemukan ulang — **jangan diulang**:
- Agent dikirim sebagai **pickle**, jadi paket `app` wajib ikut lewat `extra_packages`.
  Tanpa itu container gagal start: `ModuleNotFoundError: No module named 'app.agents'`.
- Di jalur sumber, entrypoint wajib objek **`AdkApp`** (lihat `app/agents/aplikasi.py`),
  bukan agent mentah, dan `class_methods` wajib diisi sendiri.
- ⚠️ **`build_options` / `installation_scripts` divalidasi SDK lalu tidak pernah
  dikirim ke API** — di kedua jalur. Tidak ada `buildOptions` di payload SDK, dan
  log build tidak memuat eksekusi skrip. **Jangan mengandalkannya** untuk memasang
  dependensi sistem.

⚠️ Chromium **tidak bisa** dipasang lewat jalur bawaan Agent Engine (installation
script diabaikan; pemasangan runtime melebihi anggaran waktu permintaan).
**Jalan keluarnya: container sendiri** — lihat bagian berikut.

### Cloud Run — hidup dan terbukti (7 Agt)

`https://arka-110352541672.us-central1.run.app` · region `us-central1` ·
image `us-central1-docker.pkg.dev/ebco-aihack-amanda/arka/arka:v1`

**Rantai penuh sudah berjalan di sana**: reporter menerbitkan PDF (88 KB, dirender
Chromium di dalam container), penilai memeriksa, `selesai` menghentikan putaran.

Resep dan jebakannya:
- `Dockerfile` — `python:3.12-slim` + `playwright install --with-deps chromium`.
  **2,53 GB**; image resmi Playwright dipakai lebih dulu tapi 4,27 GB karena memuat
  tiga peramban. Versi biner peramban harus sepadan dengan paket `playwright`.
- `adk_agents/` — ADK menuntut satu direktori per agent berisi `agent.py`.
  Isinya pembungkus tipis; logika tetap di `app/agents/`.
- Mac ARM → Cloud Run butuh **`--platform linux/amd64`**. `gcloud builds submit`
  ditolak `PERMISSION_DENIED` walau peran `editor`, jadi dipakai `docker buildx`
  lalu push langsung ke Artifact Registry.
- ⚠️ **gcloud crash di `gcloud run deploy`** (`unsupported operand type(s) for |`)
  karena Python 3.9 bawaannya. Obatnya:
  `CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.12 gcloud run deploy ...`

⚠️ **Agent Engine lewat `image_spec` — dicoba 11 Agt, buntu.** Build berhasil dan
resource hidup, tetapi `class_methods` kosong dan `agent_framework: custom`,
sehingga `:query` maupun `:streamQuery` menjawab 404. Container kita melayani
`adk api_server`; runtime itu menuntut kontrak HTTP-nya sendiri. Yang belum
dicoba dan jadi langkah berikutnya: `agent_server_mode` beserta kontrak server
yang diminta Agent Engine. Resource uji sudah dihapus — **runtime demo adalah
Cloud Run**.

### Lapisan pelaporan — sudah jadi, kontraknya kunci

`Finding` (`app/reporting/finding.py`) adalah **satu-satunya** masukan reporter.
Investigator cukup menulis objek itu ke session state kunci `finding`; tidak ada
baris di reporter yang perlu berubah.

| Berkas | Peran |
|---|---|
| `app/reporting/finding.py` | Kontrak serah-terima investigator → reporter |
| `app/reporting/blocks.py` | 8 blok, dirakit deterministik dari `Finding` |
| `app/reporting/dokumen.py` | Registry jenis + `KonteksDokumen` (kelengkapan surat) |
| `app/reporting/memo.py` | Render HTML (kerja internal) + PDF A4 (untuk manusia) |
| `app/reporting/grafik.py` | 3 grafik SVG inline, dirakit dari data |
| `app/reporting/lencana.py` | Lencana unit dibangkitkan — tidak ada logo tersimpan |
| `app/agents/qa.py` | Penilai mutu + `LoopAgent` maks 3 putaran |
| `app/reporting/templates/_blok.html.j2` | Makro isi — dipakai bersama semua jenis |
| `app/reporting/narasi.py` | Penyaring narasi model — kalimat berangka dibuang |
| `app/agents/reporter.py` | Agent ADK, 3 tool |
| `app/synthetic/finding_contoh.py` | Temuan contoh — uji tanpa DB dan tanpa investigator |

Tiga jenis dokumen: `memo`, `nota_dinas`, `laporan`. Isi dan angka identik;
yang berbeda hanya chrome dan kebijakan blok bawaan. Jenis keempat = satu template
chrome + satu entri registry.

Penegakan prinsip (bukan sekadar instruksi prompt):
- Pilihan blok model diperlakukan **usulan** — id asing diabaikan, blok kosong disaring,
  `ringkasan` dan `sitasi` disisipkan paksa.
- Angka dirender lewat filter `angka` dari data; narasi model tidak punya jalur mengubahnya.
- Kalimat narasi bermuatan angka **dibuang di `pilih_blok`** — termasuk angka dalam
  bentuk kata ("dua kandidat" sama terlarangnya dengan "2 kandidat"). Kebocoran nyata
  yang memicu penjaga ini terjadi pada uji hidup pertama. `satu` dan bilangan tingkat
  (`kedua`, `ketiga`) sengaja dilewatkan — nyaris selalu idiomatik.
- `DokumenTanpaSitasi` menolak penerbitan tanpa rujukan (FR-009, prinsip II).

69 tes hijau, ruff bersih pada berkas yang disentuh:
`test_reporting_memo.py` (33) · `test_narasi.py` (18) · `test_reporter_agent.py` (18).

Render contoh tanpa DB: `uv run python scripts/render_contoh.py` → `out/`.
PDF **berfungsi** (chromium terpasang); jalur mundur ke HTML tetap ada di
`terbitkan_dokumen` kalau peramban hilang di lingkungan lain.

**D3:** Investigator penuh + jejak penalaran + sitasi · chat
**D4:** Memo + criticality + radius dampak — 🎯 **demo end-to-end harus jalan hari ini**
**D5:** Infografis · Curator · **rekam video** · bekukan fitur
**D6:** Submission

### Urutan pemotongan kalau tertinggal
1. PPTX → buang · 2. Curator → skrip batch sederhana · 3. Infografis → satu persona,
blok paling sedikit

Yang **tidak pernah** dipotong dari infografis: Prinsip I. Kalau waktunya habis,
yang hilang adalah persona kedua dan blok pilihan — bukan kesetiaan angka.

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
- Model: **`gemini-3.6-flash`**, lokasi **`global`** (bukan region)
- Project GCP: **`ebco-aihack-amanda`** — satu sumber kebenaran di `.env`;
  `Settings` membacanya, `terapkan_env_vertex()` menyalinnya ke `os.environ`
  karena `google-genai` membaca lingkungan, bukan objek Settings
- `app/synthetic/` adalah alat waktu-pengembangan — tidak ikut ter-deploy ke Agent Engine

### 🔤 Bahasa — berubah 7 Agt

**Seluruh kode, komentar, docstring, dan prompt agent memakai bahasa Inggris.**
Termasuk nama modul, fungsi, dan variabel. Ini menggantikan konvensi sebelumnya
yang memakai bahasa Indonesia.

Yang **tetap** bahasa Indonesia: isi dokumen yang diterbitkan ARKA (memo, nota
dinas, laporan) dan teks yang dibaca pengguna akhir — pembacanya reliability
engineer Indonesia. Jadi prompt ditulis dalam bahasa Inggris, tetapi memerintahkan
model menjawab dan menulis dokumen dalam bahasa Indonesia.

Kode yang ditulis sebelum 7 Agt masih berbahasa Indonesia (`app/reporting/`,
`app/synthetic/`, `app/agents/`, `tests/`).

**Cara migrasinya — bertahap per modul, satu modul utuh sekali jalan.** Berkas
setengah-Inggris lebih buruk daripada berkas yang belum disentuh: pembaca tidak
tahu mana konvensi yang berlaku. Satu modul berarti berkasnya **beserta tesnya**,
termasuk nama berkas, kelas, fungsi, dan variabel.

Dikerjakan saat modul itu memang sedang disentuh untuk alasan lain — bukan
sebagai proyek tersendiri. Urutan yang masuk akal, dari yang paling jarang
berubah ke yang paling sering:

1. `app/synthetic/` — paling terisolasi, hanya alat waktu-pengembangan
2. `app/reporting/` — sudah stabil, tesnya rapat (33 + 14 + 15)
3. `app/agents/` — paling sering berubah, migrasi paling akhir

⚠️ Prompt agent ikut dimigrasi ke bahasa Inggris, tetapi **harus tetap
memerintahkan model menulis dokumen dalam bahasa Indonesia**. Menerjemahkan
prompt tanpa menambahkan perintah itu akan mengubah bahasa dokumen terbitan —
regresi yang tidak akan tertangkap tes mana pun.

### Kerangka & deployment

- **Google ADK** (Agent Development Kit) — bukan framework buatan sendiri
- Deployment: **Cloud Run** dan **Vertex AI Agent Engine**, memakai image yang sama
- Pengembangan mengikuti **Spec-Driven Development** (GitHub Spec Kit):
  spec → plan → tasks → implement. Fitur baru dimulai dari `specs/`, bukan dari kode.
