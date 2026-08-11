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
| `failure_probability` | 0,40 | Berapa kali part ini benar-benar terlibat kegagalan, ternormalisasi terhadap titik jenuh |
| `consequence` | 0,35 | Total menit downtime yang timbul ketika ia gagal, ternormalisasi terhadap titik jenuh |
| `supply_risk` | 0,25 | 0,6 × lead time ternormalisasi + 0,4 × risiko pasokan (1 / jumlah vendor) |

```
criticality = 0.40·failure_probability + 0.35·consequence + 0.25·supply_risk
```

Skornya sendiri tidak dipotong menjadi tingkat. ARKA tidak menyatakan sebuah part
"kritis" atau "normal" pada ambang tertentu, karena ambang semacam itu akan menjadi
angka yang tidak berasal dari mana pun. Yang dipakai adalah **selisih terhadap master
data**: sparepart diurutkan dari selisih terbesar, dan ditandai ketika hitungan ARKA
melampaui label statisnya.

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
| Seluruh teks, angka, label, dan sitasi — disusun kode dari `Finding`, dikirim verbatim. Urutan kartu dan posisinya pada grid — dihitung dari urutan blok yang disetujui Reporter | Bentuk visual, ilustrasi, dan penataan halus di dalam tiap kartu |

Pengecualian ini dicatat di Constitution proyek dan disertai tiga imbangan yang wajib, bukan pilihan:

1. **Tidak ada nilai yang hanya dibawa oleh bentuk.** Setiap angka juga tertulis di sebelah grafiknya, sehingga kesalahan penggambaran tidak pernah menjadi kesalahan angka. Nama besarannya pun ditentukan kode, bukan halaman: angka tanpa nama adalah pertanyaan terbuka, dan pada satu run halaman menjawabnya sendiri dengan menamai skor kekritisan "Kritikalitas" — kata yang tidak ada di temuan mana pun.
2. **Penilai membaca halaman yang sudah tergambar.** Bukan promptnya — gambarnya. Setiap string yang terlihat dicocokkan ke isi kanvas. Yang tidak punya padanan sama sekali adalah karangan dan memicu penggambaran ulang; yang hanya salah eja dari teks berwenang dicatat sebagai cacat cetak dan tidak memblokir. Pembedaan itu bukan pelonggaran: menggambar ulang tidak dapat diandalkan memperbaiki satu huruf yang hilang, dan memperlakukan keduanya sama membuat halaman yang setia gagal terbit karena "Catatan Teknis" tertulis untuk "Catatan Teknisi".
3. **Memo tetap catatan resmi.** Angka yang dipakai mengambil keputusan dirujuk dari memo, bukan dari infografis.

Imbangan kedua bukan formalitas. Pada satu run, penggambar menambahkan chip identitas "Lokasi Fungsional" yang diambilnya dari judul dokumen sitasi lalu disajikan sebagai fakta tentang aset. Pemeriksaan yang membandingkan isi kanvas terhadap temuan meloloskannya — string itu memang ada di temuan. Hanya membaca halamannya yang menangkapnya.

Bentuk visual tiap kartu pun tidak dipilih dari nama bloknya, melainkan dari data yang dikandungnya. Tujuh belas pola visualisasi disaring terhadap isi kartu — berapa butir, mana yang membawa angka sungguhan, tanggal, atau tingkat — dan designer memilih dari yang tersisa. Efeknya menutup satu kelas kesalahan sejak hulu: kartu tanpa tanggal tidak pernah ditawari linimasa, sehingga tidak ada lagi halaman yang mengarang stempel waktu demi mengisi bentuk yang terlanjur dipilih. Perbandingan kekritisan pun dibawa utuh — 0,30 milik master data disandingkan dengan 0,87 hitungan ARKA — karena angka tunggal justru menyembunyikan hal yang paling layak dilihat.

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
| Runtime agent | Cloud Run · Vertex AI Agent Engine |
| Keluaran dokumen | ADK Artifacts (`GcsArtifactService`) |
| Model penalaran | Gemini di Vertex AI |
| Knowledge graph | BigQuery (edge list + recursive CTE) · Apache AGE 1.6 di jalur lokal |
| Pencarian semantik | BigQuery `VECTOR_SEARCH` · `gemini-embedding-2` (3072 dimensi) |
| Database | BigQuery (sumber) · PostgreSQL 16 (generator sintetis, tes) |
| Backend | FastAPI, SQLAlchemy (async), Alembic |
| Renderer dokumen | Jinja2 + SVG inline, dicetak Chromium via Playwright |
| Penggambar infografis | `gpt-image-2` (OpenAI), dipagari gerbang mutu berbasis vision |
| Pembaca halaman | Gemini vision — mentranskripsi halaman, kode yang menilai |
| Pustaka desain | 44 aset YAML tervalidasi saat startup |
| Kontainerisasi | Docker, Docker Compose |
| Kualitas kode | pytest, ruff |
| Deployment | **Cloud Run** — rantai penuh hidup, membaca dari BigQuery · jalur Agent Engine terbukti dan tercatat |

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
# Rantai penuh: pindai armada, selidiki yang terpilih, terbitkan dokumen
python scripts/run_chain.py

# Satu aset tertentu
python scripts/run_chain.py --tag PLT-U/FIL-207

# Pemindaian terjadwal — deterministik, tanpa memanggil model
python scripts/pindai_terjadwal.py

# Membuktikan jalur produksi di BigQuery Graph
python scripts/uji_bigquery_graph.py
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

Data mencakup perusahaan FMCG fiktif dengan **5 pabrik**, **505 equipment**, **3.009 work order**, **1.835 aktivitas perawatan**, **68 kegagalan**, dan **54 dokumen**, dalam rentang **3 tahun**.

Angkanya terbagi dua dengan sengaja. **Jalur emas** — 5 filler model sama di 5 pabrik, 8 kegagalan, 4 dokumen yang bisa dikutip — adalah data yang penalarannya diuji di atasnya, dan setiap angkanya dikalibrasi. **Volume latar** — 500 equipment, 3.000 work order, dan 50 laporan inspeksi dari tipe mesin lain — ada untuk menguji penyaringnya, bukan penalarannya.

Keduanya dipisahkan secara konstruksi, bukan lewat pemeriksaan sesudahnya: model mesin, jenis komponen, dan kepemilikan work order latar dibuat tidak beririsan dengan jalur emas, sehingga volume latar **tidak punya jalur** untuk menggeser skor. Setelah volume ditambahkan, seluruh angka demo tidak bergerak satu digit pun.

Beberapa keputusan yang disengaja dalam pembangkitan data:

- **Armada mesin seragam antar pabrik** — model mesin yang sama terpasang di beberapa pabrik, sehingga penemuan preseden lintas pabrik menjadi bermakna
- **Data sengaja dibuat tidak bersih** — sebagian work order tanpa referensi equipment, typo ala OCR, kode katalog ambigu. Tanpa ini, kapabilitas Curator dan penanganan kualitas data tidak dapat diperagakan
- **Taksonomi mengikuti pola standar industri** untuk failure mode, cause, dan damage

---

## Jalur produksi: BigQuery

Prototipe dikembangkan di **PostgreSQL + Apache AGE**. Kini **seluruh 39 tabel kanonik ada di BigQuery**, dan rantai deteksi berjalan penuh dari sana.

Perpindahannya murah karena satu batas arsitektur: `app/detection/store.py` adalah **satu-satunya tempat yang tahu penyimpanan mana yang menjawab**. Seluruh lapisan di atasnya — skor, perakitan temuan, agent, renderer — bekerja pada dataclass.

```bash
python scripts/run_chain.py                       # PostgreSQL + AGE
ARKA_STORE=bigquery python scripts/run_chain.py   # BigQuery
```

**Paritas diukur, bukan diklaim.** Rantai yang sama atas data yang sama, dari kedua penyimpanan: `0,9071` dan `0,8819`, eskalasi pada margin `0,0252`, 5 preseden, 8 sitasi, kekritisan seal `0,8667`. Identik sampai digit terakhir.

### Yang kami temukan tentang graph di BigQuery

Asumsi awal kami — "GQL butuh Enterprise, jadi BigQuery Graph tidak terpakai" — ternyata benar separuh, lalu ternyata tidak cukup. Diuji langsung, on-demand, tanpa reservation:

| | On-demand |
|---|---|
| `CREATE PROPERTY GRAPH` | ✅ berhasil |
| `GRAPH … MATCH …` — sintaks GQL penuh | ❌ menuntut edisi Enterprise |
| `GRAPH_EXPAND(...)` | ⚠️ berhasil, tapi **bukan fungsi traversal** |

`GRAPH_EXPAND` menolak lebih dari 10 node table, menuntut graph bermuara tunggal, dan **menolak jalur konvergen**:

> *The subgraph reachable from start node 'failure_events' contains a convergent path involving node 'equipment'.*

Equipment dicapai lewat komponennya **dan** secara langsung, jadi graph ini konvergen secara bawaan — tidak ada perampingan yang memperbaikinya. `GRAPH_EXPAND` adalah pemipih snowflake untuk satu tabel fakta, bukan penelusur graph.

### Jalan keluarnya: edge list + recursive CTE

Graph disimpan sebagai daftar edge terpadu (**6.474 node, 9.975 edge, 13 label node, 16 jenis edge**) dan ditelusuri dengan recursive CTE — jalan penuh di on-demand, tanpa reservation.

Kedalaman menjadi parameter, bukan sifat skema, dan **jalurnya dikembalikan sebagai data**:

```
PLT-U/FIL-207 -[MEMILIKI_KOMPONEN]-> seal -[DIPASOK_OLEH]-> SP-SEAL-8801
              -[DIPASOK_OLEH⁻¹]-> seal -[MEMILIKI_KOMPONEN⁻¹]-> PLT-G/FIL-412
```

Itulah bagian yang membuatnya bisa diperiksa, bukan sekadar dipercaya. Traversal yang hanya mengembalikan tujuannya meminta untuk dipercaya; yang mengembalikan jalurnya bisa dibantah.

Edge ditelusuri **dua arah**, langkah balik ditandai `⁻¹`. Searah saja setiap rute buntu di sparepart pada hop ketiga — dan arah balik itulah arah pertanyaan rantai pasok berjalan: diberi sebuah part, apa lagi yang memakainya.

Terukur: 1.086 jalur pada 4 hop, 1.580 pada 5 hop, dalam hitungan detik.

---

## Batasan yang diketahui

Disampaikan terbuka:

1. **Data di BigQuery adalah salinan.** Rantai penuh berjalan di Cloud Run membaca dari BigQuery, tetapi isinya disalin dari PostgreSQL lewat langkah sinkronisasi. Bila jalur emas berubah tanpa sinkronisasi dijalankan, salinan itu basi tanpa peringatan. Pada penerapan nyata BigQuery menjadi sumber langsung dan langkah ini hilang.
2. **Runtime utama adalah Cloud Run**, dan di sana rantai penuh berjalan: memindai armada, menyelidiki, menerbitkan PDF, serta menjawab pertanyaan bebas — seluruhnya membaca dari BigQuery. Jalur deploy ke Agent Engine sudah dibuktikan — agent hidup, menjawab, dan memanggil tool — dan resepnya tersimpan di `scripts/deploy_hello.py` serta `scripts/deploy_sumber.py`. Yang belum terpecahkan: Agent Engine dengan container sendiri (`image_spec`) berhasil dibangun tetapi tidak mengekspos permukaan query, karena container kami melayani `adk api_server` sementara runtime itu menuntut kontrak HTTP-nya sendiri. Karena render PDF menuntut Chromium yang hanya ada di image kami, runtime yang dipakai adalah Cloud Run.
3. **Urutan penelusuran bersifat tetap.** Yang diputuskan model adalah kasus mana yang dikejar, seberapa dalam, dan kapan berhenti — bukan rute traversalnya. Ini pilihan sadar demi jejak yang dapat diaudit, dan menjadi batasan yang jujur untuk disebut.
4. **Lapisan ingestion belum generik.** Saat ini data ditulis langsung ke tabel kanonik; setiap sistem sumber baru memerlukan konektor tersendiri.
5. **Curator belum dibangun.** Persetujuan pemetaan masih sepenuhnya manual.
6. **Biaya per investigasi belum diukur secara sistematis.** Yang sudah dipisahkan: pemindaian armada tidak memanggil model sama sekali, sehingga biaya hanya muncul saat ada yang benar-benar diselidiki.
7. **Skala pengujian menengah, bukan produksi.** 505 equipment dan 3.009 work order — cukup untuk membuktikan penyaringan bekerja (20 kegagalan terbuka dipindai, 18 ditolak) dan traversal tetap cepat, tetapi masih dua kali lipat lebih kecil dari estate nyata. Perilaku pada ratusan ribu baris belum diuji.
8. **Pemasangan sparepart tercatat, tetapi nomor batch material belum.** `activity_spare_parts` mencatat pekerjaan mana yang memakai part apa, berapa banyak, dan kapan — sehingga "apa lagi yang memakai part ini" dijawab dari kejadian, bukan dari kecocokan jenis komponen. Yang belum ada adalah **nomor batch**: pertanyaan "unit mana lagi yang memakai batch material yang sama" masih berhenti di tingkat part.
9. **Pemasok tier-2 dan tier-3 belum dimodelkan** — radius dampak berhenti di pemasok langsung.
10. **Traversal multi-hop belum dipakai agent mana pun.** Lapisannya jalan dan teruji sampai lima hop, tetapi rantai deteksi masih menjawab keempat pertanyaannya lewat join SQL — dan paritas antar penyimpanan bergantung pada itu. Menyambungkannya ke radius dampak sparepart menyentuh angka yang masuk ke memo, jadi menuntut pengujian paritas ulang, bukan sekadar tes hijau.
11. **Sintaks GQL penuh tetap di luar jangkauan.** `GRAPH … MATCH …` menuntut reservation Enterprise. Recursive CTE menghasilkan traversal yang setara di on-demand dan justru mengembalikan jalurnya, tetapi ia SQL — bukan bahasa graph, dan tidak sepadan ekspresifnya untuk pola yang rumit.
12. **Ambang kemiripan tidak memisahkan bersih, dan kami mengukurnya.** `MIN_SIMILARITY = 0,60` atas korpus 54 dokumen: pertanyaan dalam domain mencapai 0,5140–0,7703, pertanyaan di luar domain 0,5018–0,5692. **Kedua rentang bertumpang tindih** — satu pertanyaan dalam domain menemukan dokumen yang benar dan tetap skornya 0,5140, di bawah pertanyaan omong kosong terbaik. Pada korpus empat dokumen celahnya terlihat bersih; itu properti korpus kecilnya, bukan properti sistem. Ambang 0,60 dipertahankan sebagai pilihan **presisi di atas recall**: pertanyaan yang jauh dari kata-kata dokumennya dijawab dengan diam, bukan dengan tebakan paling mendekati. Perbaikan sebenarnya bukan konstanta yang lebih baik melainkan uji relatif — selisih hit teratas terhadap sisanya, atau rerank — karena "apakah ini yang paling cocok" dan "apakah ini cukup cocok" adalah dua pertanyaan berbeda.

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
| 1 | Lapisan graph di BigQuery untuk estate yang datanya sudah di sana — porting terbatas pada satu berkas |
| 2 | Lapisan ingestion generik dengan konektor yang dapat dikonfigurasi |
| 3 | Curator sepenuhnya agentic |
| 4 | Pengukuran biaya dan latensi per investigasi |
| 5 | Pemodelan pemasok tier-2 dan tier-3 |
| 6 | Analisis bottleneck lini produksi (perluasan dari kegagalan aset ke keterlambatan produksi) |

---

## Lisensi

`[tentukan]`
