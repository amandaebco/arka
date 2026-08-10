# ARKA — Asset Reliability Knowledge Agent

**EBCO AI Hackathon 2026 · Kategori B — AI Agent · Tema: Knowledge Management Solution**

> Agent otonom yang menyingkap akar masalah keandalan mesin, dengan bukti yang bisa ditelusuri.

| | |
|---|---|
| **Peserta** | `[nama]` (solo) |
| **Repository** | `[link repo]` |
| **Aplikasi berjalan** | `[link deployment]` |
| **Video demo** | `[link video]` |

---

## Ringkasan

ARKA adalah sistem AI agent otonom untuk analisis akar masalah keandalan mesin di manufaktur multi-pabrik.

Berbeda dari chatbot RAG yang merangkum dokumen, ARKA **menalar di atas knowledge graph**: ia menelusuri rantai hubungan antara pabrik, lini produksi, mesin, komponen, riwayat work order, laporan inspeksi, dan rantai pasok sparepart. Kemampuan ini memungkinkannya menemukan hal yang mustahil ditemukan pencarian teks — misalnya bahwa gejala yang muncul di satu pabrik hari ini pernah terjadi dan terselesaikan di pabrik lain delapan bulan lalu.

ARKA bekerja **proaktif**. Ia memindai seluruh armada tanpa ada yang menunjuk kasusnya, menyaring mana yang layak diselidiki — sekaligus melaporkan yang diabaikan beserta alasannya — lalu menelusuri yang terpilih dan merangkainya menjadi dokumen siap pakai dengan setiap klaim membawa sitasinya.

---

## Latar belakang

Gelombang solusi AI enterprise hari ini didominasi satu pola: **chatbot RAG di atas tumpukan dokumen**. Pola ini bekerja baik untuk pertanyaan yang jawabannya berada di dalam satu dokumen — apa isi SOP ini, bagaimana prosedur itu.

Tapi ia buntu pada kelas pertanyaan yang berbeda: **pertanyaan yang jawabannya berada di hubungan antar dokumen.** Ketika seorang engineer bertanya "kenapa mesin ini rusak lagi", jawabannya tidak berada di satu tempat. Ia tersebar di work order tahun lalu, di laporan inspeksi pabrik lain, di riwayat penggantian komponen, dan di catatan pengadaan sparepart. Pencarian berbasis kemiripan teks tidak bisa menyatukannya, karena yang menghubungkan bukanlah kesamaan kata, melainkan **kesamaan struktur**.

Knowledge graph sering disebut sebagai jawabannya. Namun dalam praktik, knowledge graph umumnya berhenti sebagai penyimpanan atau alat visualisasi — sesuatu yang dilihat manusia, bukan sesuatu yang ditelusuri mesin secara mandiri.

Proyek ini berangkat dari satu pertanyaan:

> **Kalau sebuah agent diberi knowledge graph dan kebebasan menentukan jalur penelusurannya sendiri, seberapa jauh ia bisa sampai — dan apakah kesimpulannya bisa dipertanggungjawabkan?**

Tiga hal yang ingin dibuktikan:

1. **Penalaran multi-hop yang otonom** — agent menentukan langkah berikutnya dari hasil langkah sebelumnya, bukan menjalankan urutan yang sudah ditetapkan
2. **Inisiatif** — agent menemukan hal yang layak diperhatikan tanpa menunggu ditanya
3. **Keterlacakan** — setiap kesimpulan membawa bukti sampai ke kalimat di dokumen asli

Keandalan aset manufaktur dipilih sebagai lahan uji karena tiga alasan: masalahnya nyata dan terukur dalam biaya downtime, struktur datanya memang berbentuk graph, dan konsekuensi kesalahannya cukup serius sehingga menuntut sistem yang jujur tentang ketidakpastiannya — yang justru menjadi bagian menarik dari perancangannya.

---

## Masalah yang diselesaikan

> **Kegagalan yang sama terjadi berulang di pabrik yang berbeda, dan setiap kali dibayar dari nol.**

Perusahaan manufaktur multi-pabrik biasanya sudah memiliki jawabannya — tersimpan di work order tahun lalu, di laporan inspeksi pabrik sebelah, di kepala teknisi yang sudah pindah. Masalahnya bukan data tidak ada, melainkan **pengetahuan itu tidak mengalir**.

Konsekuensinya diperbesar oleh rantai pasok: ketika mesin akhirnya rusak, baru ketahuan sparepart-nya dipasok vendor tunggal dengan lead time berminggu-minggu.

### Masalah kedua: kekritisan sparepart yang diwarisi, bukan dihitung

Rata-rata manufaktur padat aset menyimpan **20–30% inventori MRO berlebih**, sementara tetap menghadapi **risiko stockout pada 10–15% sparepart kritis**.

Penyebabnya diakui luas di industri: sparepart rutin diberi tingkat kekritisan mengikuti aset induknya — mengabaikan lead time, ketergantian, dan dampak kegagalan sebenarnya. Akibatnya apa pun yang berlabel "kritis" ditumpuk tanpa pandang bulu, sementara yang benar-benar berisiko justru kosong.

### Kenapa tool yang ada tidak menyelesaikannya

| Pendekatan | Keterbatasan |
|---|---|
| CMMS / ERP | Mencatat kejadian, tidak menghubungkan **pola** antar pabrik |
| Dashboard BI | Menjawab "berapa banyak", bukan "kenapa kasus ini" |
| Document search / RAG | Menemukan teks yang **mirip**, bukan kemiripan **struktural** |
| Keahlian senior | Nyata, tapi tidak terskala — dan hilang saat orangnya pergi |

Pengetahuan paling berharga di manufaktur tidak berada di dalam satu dokumen, melainkan **di hubungan antar dokumen**. Di situlah knowledge graph diperlukan, dan di situlah pencarian berbasis kemiripan teks berhenti.

---

## Apa yang dilakukan ARKA

### 1. Menemukan tanpa diminta
Memindai seluruh armada tanpa ada yang menunjuk kasusnya, lalu mengangkat yang layak diperhatikan — dan **melaporkan berapa yang diabaikan beserta alasannya**, supaya penyaringnya bisa dibantah.

Pemindaian dijalankan `scripts/pindai_terjadwal.py` dan dapat dipasang di penjadwal mana pun. Pemindaian **tidak memanggil model sama sekali**: ia murni deterministik, sehingga berjalan tiap pagi nyaris tanpa biaya. Model baru dilibatkan ketika ada yang benar-benar perlu diselidiki.

### 2. Menyelidiki lintas pabrik, dengan jejak yang bisa diaudit
Menelusuri dari gejala ke kasus tuntas pada model mesin yang sama di pabrik lain, ke penyebab terverifikasinya, ke komponen dan sparepart-nya, lalu ke jadwal perawatan berikutnya.

Urutan penelusuran itu **tetap dan dapat direproduksi**; yang diputuskan model adalah kasus mana yang dikejar, seberapa dalam, dan kapan berhenti. Ini pilihan yang disengaja: penelusuran yang jalurnya berubah tiap dijalankan tidak bisa diaudit, dan bukti yang tidak bisa diaudit tidak layak dipakai mengambil keputusan perawatan. Setiap langkah tercatat di jejak penalaran yang ikut tercetak di laporan.

### 3. Menunjukkan bukti
Setiap kesimpulan membawa sitasi ke dokumen sumber beserta kalimat yang dikutip, dan nomor halaman **bila dokumen sumbernya memang mencatat halaman**. Sitasi yang tidak diketahui halamannya dibiarkan tanpa nomor — menomori halaman yang tidak tercatat akan membuat sitasi tampak lebih presisi daripada buktinya.

Dokumen tanpa satu pun sitasi **ditolak terbit**, bukan diterbitkan dengan catatan.

### 4. Menghitung ulang kekritisan sparepart
Menelusuri dari komponen ke sparepart ke pemasoknya, lalu menyebar lewat jenis komponen ke seluruh aset yang memakai part yang sama di pabrik lain — dan dari situ **menghitung ulang kekritisannya** dari kondisi aktual, bukan mewarisinya dari aset induk.

Pada jalur demo, seal yang ditandai master data **0,30** dihitung ARKA **0,87**: vendor tunggal, lead time enam minggu, dan terpasang di **kelima pabrik** — bukan hanya di dua tempat ia sudah pernah gagal.

### 5. Berhenti ketika tidak yakin
Ketika dua kandidat penyebab berdekatan, ARKA **tidak menebak** — ia mengeskalasi ke manusia dengan pertanyaan yang spesifik.

### 6. Menyusun memo, nota dinas, dan laporan
Merangkai investigasi menjadi dokumen berkop — temuan beserta skornya, preseden dan tindakan yang dulu berhasil, dampak rantai pasok, jejak penalaran, dan rekomendasi berprioritas. Isi dan angkanya identik di ketiga bentuk; yang berbeda hanya derajat formalitas dan blok bawaannya. Setiap klaim membawa sitasinya.

Memo juga menandai **konflik waktu yang tidak terlihat oleh sistem manapun secara sendirian**: perencana perawatan tahu kapan jendela berikutnya dibuka, perencana material tahu lead time-nya, dan keduanya hidup di sistem yang tidak pernah bicara. Pada jalur demo, perawatan dijadwalkan 28 hari lagi sementara lead time seal enam minggu — ARKA menghitung selisih 14 hari dan menaikkan pengadaan menjadi tindakan segera.

---

## Cara kerja mekanisme deteksi

Bagian ini sengaja dijelaskan terbuka, karena kredibilitas sistem bertumpu padanya.

### Sinyal
Himpunan gejala dari notifikasi yang sedang terbuka dibandingkan dengan failure event historis pada **model mesin yang sama** di seluruh pabrik.

### Skor

| Komponen | Bobot | Definisi |
|---|---|---|
| `symptom_overlap` | 0,50 | \|gejala sekarang ∩ gejala historis\| / \|gejala historis\| |
| `component_match` | 0,20 | 1,0 bila komponen sama; 0,5 bila satu subsistem |
| `corroboration` | 0,20 | min(jumlah kasus serupa / 3 , 1,0) |
| `recency` | 0,10 | peluruhan terhadap usia kasus historis |

### Ambang keputusan

| Kondisi | Aksi |
|---|---|
| skor ≥ 0,65 | Laporkan sebagai temuan |
| dua kandidat selisih ≤ 0,05 | Eskalasi ke manusia |
| skor < 0,50 | Abaikan |

Dengan demikian skor `0,72` memiliki arti yang dapat diperiksa: *tiga dari empat gejala cocok, pada model mesin yang sama, dengan dua kasus historis yang menguatkan.*

### Pembagian peran: deterministik vs model bahasa

| Deterministik | Gemini |
|---|---|
| Pencocokan pola & penghitungan skor | Memutuskan jalur penelusuran berikutnya |
| Traversal graph | Menafsirkan teks bebas notifikasi |
| Ambang & aturan eskalasi | Menyusun narasi & laporan |

Ini keputusan desain yang disengaja. Skor kemiripan harus **dapat diaudit dan direproduksi** — menempatkan model bahasa di sana akan membuat sistem tidak dapat dipertanggungjawabkan. Kecerdasan agent berada di orkestrasinya, bukan di penghitungan skornya.

---

## Dynamic spare part criticality

Praktik industri menilai kekritisan sparepart di tiga dimensi: probabilitas kegagalan, konsekuensi kegagalan, dan risiko pasokan. Ketiganya sudah tersedia di dalam graph, sehingga kekritisan dapat dihitung ulang secara dinamis alih-alih diwarisi dari aset induk.

| Dimensi | Bobot | Sumber |
|---|---|---|
| `failure_probability` | 0,40 | Skor deteksi pola (lihat bagian sebelumnya) |
| `consequence` | 0,35 | (pabrik terekspos / total pabrik) × kekritisan lini |
| `supply_risk` | 0,25 | Lead time ternormalisasi + penalti vendor tunggal |

```
criticality = 0.40·failure_probability + 0.35·consequence + 0.25·supply_risk
```

| Skor | Tingkat | Rekomendasi |
|---|---|---|
| ≥ 0,70 | Kritis | Amankan stok / cari sumber alternatif |
| 0,40–0,69 | Perhatian | Pantau, tinjau siklus berikutnya |
| < 0,40 | Normal | — |

Keluaran yang paling berguna bukan skornya, melainkan **selisihnya terhadap label statis di master data** — misalnya sebuah part berlabel non-kritis yang dinaikkan menjadi kritis karena probabilitas kegagalannya meningkat, beberapa pabrik terekspos, dan pemasoknya tunggal.

---

## Arsitektur

```
        ┌──────────────────────────────────────────────────────┐
        │        Cloud Run · Vertex AI Agent Engine            │
        │  Scout → Investigator → Reporter → Designer          │
        │  Curator (ortogonal)                                 │
        └──────────────────────────┬───────────────────────────┘
                                   │  Finding (kontrak tunggal)
        ┌──────────────────────────┴───────────────────────────┐
        │        Lapisan deteksi — deterministik, nol model    │
        │  skor kemiripan · ambang keputusan · kekritisan      │
        │  dinamis · konflik lead time vs jendela perawatan    │
        └──────────────────────────┬───────────────────────────┘
                                   │
        ┌──────────────────────────┴───────────────────────────┐
        │        PostgreSQL 16 + Apache AGE 1.6                │
        │   public (tabel kanonik) → arka_kg (proyeksi graph)  │
        │   + pgvector — pencarian titik masuk semantik        │
        └──────────────────────────┬───────────────────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │  Renderer: PDF · SVG · HTML  │
                    └──────────────────────────────┘
```

Penelusuran rantai deteksi berjalan di atas **tabel kanonik**, bukan Cypher. Proyeksi AGE ada dan dipakai untuk pertanyaan yang menuntut kedalaman sembarang; relasi yang dibutuhkan jalur ini semuanya berjarak satu sampai dua join, dan menambah dialek kueri kedua di jalur kritis akan membeli kedalaman yang tidak dipakai sambil menambah satu mode kegagalan — proyeksi basi yang menghasilkan jawaban salah secara diam-diam, bukan galat.

### Sistem multi-agent

Lima agent, masing-masing dengan satu keputusan yang jelas miliknya dan titik serah-terima yang eksplisit:

| Agent | Keputusan | Serah-terima |
|---|---|---|
| **Scout** | Memindai kegagalan terbuka di seluruh armada, memutuskan mana yang layak diselidiki — dan melaporkan yang diabaikan | → Investigator |
| **Investigator** | Memutuskan kasus mana yang dikejar, seberapa dalam menelusuri, dan kapan mengeskalasi ke manusia | → Reporter |
| **Reporter** | Memutuskan isi dokumen dan urutan prioritasnya | → memo / laporan, Designer |
| **Designer** | Memutuskan penekanan visual dan bentuk visual tiap blok | → infografis |
| **Curator** | Loop terpisah. Memutuskan pemetaan mana yang aman disetujui otomatis | → proyeksi ulang graph |

`Scout → Investigator → Reporter → Designer` membentuk rantai; `Curator` berjalan ortogonal.

Batas antara Reporter dan Designer dijaga ketat: pemilihan blok tetap milik Reporter, dan Designer menerimanya sebagai masukan. Spesifikasi penyajian yang mencoba menambah blok di luar pilihan Reporter ditolak validator sebelum sempat dikompilasi — dua modul tidak boleh memiliki keputusan yang sama.

Dua di antaranya berpasangan dengan penilai dalam `LoopAgent` berbatas tiga putaran: Reporter dengan penilai dokumen, Designer dengan penilai visual. Penilai tidak pernah menyunting; ia menuliskan masukan, dan yang menerbitkan yang memperbaiki.

Sistem dibangun di atas **Google ADK**, yang menyediakan komposisi multi-agent hierarkis sebagai primitif bawaan — sehingga pemisahan peran di atas didukung framework, bukan konvensi penamaan.

### Keluaran: satu temuan, tiga renderer

Investigator menghasilkan objek `Finding` terstruktur; Reporter memutuskan blok mana yang masuk dan urutannya, lalu renderer mengubahnya menjadi bentuk yang sesuai penerimanya. Seluruhnya dikirim melalui **ADK Artifacts**.

Kontrak `Finding` itulah yang membuat lapisan-lapisan ini bisa dikerjakan terpisah: ketika Investigator akhirnya tersambung, tidak ada satu baris pun di lapisan pelaporan yang perlu berubah.

| Keluaran | Format | Penerima |
|---|---|---|
| Memo investigasi | PDF berkop | Reliability engineer — tindakan segera |
| Nota dinas | PDF berkop, kelengkapan surat | Korespondensi antar unit |
| Laporan investigasi | PDF, seluruh blok termasuk jejak penalaran | Pembaca yang ingin mengaudit |
| Infografis | PNG | Manajemen — ringkasan visual |
| Dashboard | HTML interaktif | Tinjauan cepat di peramban |

**Untuk dokumen bukti — memo, nota dinas, laporan — seluruh angka, grafik, dan diagram di-render secara deterministik dari data.** Model bahasa hanya menyusun kalimat narasinya. Ini konsisten dengan mekanisme deteksi: model tidak ditempatkan di jalur yang menuntut akurasi angka.

**Infografis adalah satu-satunya pengecualian, dan cakupannya sempit.** Halamannya digambar model gambar, karena tata letak poster yang enak dibaca sulit dicapai dengan renderer deterministik dalam waktu yang tersedia. Yang dikecualikan hanya penggambarannya:

| Tetap deterministik | Boleh dari model |
|---|---|
| Seluruh teks, angka, label, dan sitasi — disusun kode dari `Finding`, dikirim verbatim | Tata letak, bentuk visual, ilustrasi |

Pengecualian ini dicatat di Constitution proyek dan disertai tiga imbangan yang wajib, bukan pilihan:

1. **Tidak ada nilai yang hanya dibawa oleh bentuk.** Setiap angka juga tertulis di sebelah grafiknya, sehingga kesalahan penggambaran tidak pernah menjadi kesalahan angka.
2. **Penilai membaca halaman yang sudah tergambar.** Bukan promptnya — gambarnya. Setiap string yang terlihat dicocokkan ke isi kanvas; yang tidak ditemukan memicu penggambaran ulang.
3. **Memo tetap catatan resmi.** Angka yang dipakai mengambil keputusan dirujuk dari memo, bukan dari infografis.

Imbangan kedua bukan formalitas. Pada satu run, penggambar menambahkan chip identitas "Lokasi Fungsional" yang diambilnya dari judul dokumen sitasi lalu disajikan sebagai fakta tentang aset. Pemeriksaan yang membandingkan isi kanvas terhadap temuan meloloskannya — string itu memang ada di temuan. Hanya membaca halamannya yang menangkapnya.

Setiap penerbitan meninggalkan jejak audit tersendiri: temuan, isi kanvas, spesifikasi penyajian, prompt, halaman, dan hasil pemeriksaan tiap putaran. Penggambaran tidak dapat direproduksi persis; jejak inilah yang menggantikan reproduktifitas sebagai dasar pertanggungjawaban.

### Antarmuka percakapan

Tersedia antarmuka chat sebagai **jalur interogasi ke Investigator** — untuk bertanya bebas mengenai aset atau sparepart, menggali temuan lebih dalam, dan **menjawab pertanyaan eskalasi dari agent**. Mekanisme human-in-the-loop berjalan dua arah melalui jalur ini.

ARKA bukan chatbot: ia memindai armada dan mengangkat temuan tanpa menunggu ditanya, dan pemindaian itu dapat dijadwalkan. Chat adalah salah satu permukaannya, bukan identitasnya.

### Knowledge graph

Graph berjalan di **Apache AGE, di dalam PostgreSQL yang sama** dengan data operasional. Tidak ada database graph terpisah yang harus disinkronkan — satu titik kegagalan lebih sedikit, dan adopsi di lingkungan enterprise tidak menuntut lisensi maupun tim tambahan.

Ontologi mengikuti pola reliability standar industri:

```
Plant → ProductionLine → Equipment → Component
Equipment → WorkOrder → Notification → {Symptom, Cause, Damage, ObjectPart}
Equipment → FailureEvent → {Symptom, FailureMode, Cause, Damage}
Component → SparePart → Supplier
Document → Evidence → Claim → {Equipment, Component, FailureEvent}
```

### Pengaman

**ARKA tidak pernah menulis fakta ke graph.** Seluruh temuan masuk sebagai kandidat berstatus `unreviewed` yang menunggu persetujuan manusia. Status review menentukan topologi graph: relasi yang belum ditinjau menjadi edge `CANDIDATE_*`, dan hanya berubah menjadi edge final setelah disetujui.

Query yang dihasilkan model tidak dieksekusi mentah — validator membatasi bentuk query, menolak operasi tulis, dan memberi plafon `LIMIT`.

Prinsip ini mengikuti praktik yang berlaku di lingkungan industri: knowledge graph memperbaiki konteks, **tidak** memperbaiki keandalan. Keputusan akhir tetap pada manusia.

---

## Stack teknologi

| Lapis | Teknologi |
|---|---|
| Framework agent | **Google ADK (Agent Development Kit)** |
| Runtime agent | Vertex AI Agent Engine |
| Keluaran dokumen | ADK Artifacts (`GcsArtifactService`) |
| Model | Gemini |
| Knowledge graph | Apache AGE 1.6 (PostgreSQL extension) |
| Pencarian semantik | pgvector |
| Database | PostgreSQL 16 |
| Backend | FastAPI, SQLAlchemy (async), Alembic |
| Renderer dokumen | Jinja2 + SVG inline, dicetak Chromium via Playwright |
| Penggambar infografis | Model gambar, dipagari gerbang mutu berbasis vision |
| Pembaca halaman | Gemini vision — mentranskripsi halaman, kode yang menilai |
| Pustaka desain | 44 aset YAML tervalidasi saat startup |
| Kontainerisasi | Docker, Docker Compose |
| Kualitas kode | pytest, ruff |
| Deployment | Cloud Run (hidup) dan Vertex AI Agent Engine, memakai image yang sama |

---

## Menjalankan

### Prasyarat
Docker & Docker Compose · Python 3.12+ · akses project GCP dengan Vertex AI aktif

### Langkah

```bash
# 1. Konfigurasi
cp .env.example .env        # isi kredensial database & Vertex AI

# 2. Jalankan database (PostgreSQL + AGE)
docker compose up -d

# 3. Migrasi skema
alembic upgrade head

# 4. Bangkitkan data sintetis
python -m app.synthetic.generator --scale 1x

# 5. Proyeksikan graph
python -m app.graph.project

# 6. Jalankan API
uvicorn app.main:app --reload
```

### Menjalankan agent

```bash
# Investigasi satu aset
python -m app.agents.investigator --equipment <TAG>

# Siklus terjadwal (Curator + pemindaian proaktif)
python -m app.agents.scheduled_run
```

### Menjalankan test

```bash
pytest
ruff check .
```

---

## Struktur repository

```
app/
├── agents/        Scout, Investigator, Reporter, Designer, Curator, penilai
├── api/           Endpoint FastAPI
├── core/          Konfigurasi
├── db/            Sesi & health check
├── designer/      Pustaka desain, penyusun isi, komposer, penggambar, pembaca halaman
├── graph/         Retrieval core, proyeksi graph, validator Cypher, planner
├── models/        Model SQLAlchemy
├── ontology/      Definisi ontologi (YAML) — dapat ditukar per domain
├── reporting/     Blok dokumen, grafik SVG deterministik, renderer PDF
├── static/        Graph viewer
└── synthetic/     Generator data
adk_agents/        Pembungkus tipis per agent — dituntut ADK
migrations/        Migrasi Alembic
scripts/           Perkakas pengembangan & resep deploy
specs/             Spesifikasi (Spec Kit)
tests/             Test suite
```

---

## Tentang data

**Seluruh data dalam proyek ini dibangkitkan secara sintetis.** Tidak ada data nyata milik pihak mana pun yang digunakan.

Data mencakup perusahaan FMCG fiktif dengan `[N]` pabrik, `[N]` equipment, `[N]` work order, dan `[N]` notifikasi, dalam rentang waktu `[N]` tahun.

Beberapa keputusan yang disengaja dalam pembangkitan data:

- **Armada mesin seragam antar pabrik** — model mesin yang sama terpasang di beberapa pabrik, sehingga penemuan preseden lintas pabrik menjadi bermakna
- **Data sengaja dibuat tidak bersih** — sebagian work order tanpa referensi equipment, typo ala OCR, kode katalog ambigu. Tanpa ini, kapabilitas Curator dan penanganan kualitas data tidak dapat diperagakan
- **Taksonomi mengikuti pola standar industri** untuk failure mode, cause, dan damage

---

## Batasan yang diketahui

Disampaikan terbuka:

1. **Lapisan ingestion belum generik.** Saat ini menerima satu bentuk sumber; setiap sistem sumber baru memerlukan konektor tersendiri.
2. **Curator sebagian masih berbasis aturan**, belum sepenuhnya agentic.
3. **Biaya per investigasi belum diukur secara sistematis.**
4. **Skala pengujian** berada di kisaran ratusan ribu node. Perilaku pada skala jutaan node belum diuji.
5. **Graph bersifat materialized**, sehingga memerlukan proyeksi ulang setelah perubahan data. Saat ini dijalankan sebagai langkah akhir siklus Curator.
6. **Pemasok tier-2 dan tier-3 belum dimodelkan** — radius dampak berhenti di pemasok langsung.

---

## Penerapan di domain lain

Ontologi ARKA mengikuti pola pemeliharaan aset yang netral domain. Bentuk `Plant → Equipment → Component` beserta work order, failure event, symptom, dan cause berlaku identik untuk armada transportasi, alat kesehatan, infrastruktur telekomunikasi, atau fasilitas gedung.

Definisi node dan edge berada di file konfigurasi (`app/ontology/`), sehingga perpindahan domain dilakukan dengan mengganti konfigurasi — bukan mengubah kode agent.

Yang tetap netral domain: retrieval core, planner, validator, gerbang human-in-the-loop, dan renderer laporan.
Yang terikat domain: taksonomi ontologi, dan konektor ke sistem sumber.

---

## Roadmap

| Prioritas | Item |
|---|---|
| 1 | Lapisan ingestion generik dengan konektor yang dapat dikonfigurasi |
| 2 | Curator sepenuhnya agentic |
| 3 | Pengukuran biaya dan latensi per investigasi |
| 4 | Pemodelan pemasok tier-2 dan tier-3 |
| 5 | Analisis bottleneck lini produksi (perluasan dari kegagalan aset ke keterlambatan produksi) |

---

## Lisensi

`[tentukan]`
