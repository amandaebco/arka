# ARKA Constitution

ARKA — Asset Reliability Knowledge Agent — menyelidiki akar masalah kegagalan mesin
di manufaktur FMCG multi-pabrik. Prinsip di bawah ini mengikat seluruh spesifikasi,
rencana, dan implementasi turunannya. Bila sebuah rancangan berbenturan dengan salah
satu prinsip, rancangan itu yang berubah.

## Core Principles

### I. Angka Deterministik, Bahasa oleh Model (NON-NEGOTIABLE)

Pembagian ini adalah fondasi kredibilitas seluruh sistem.

| Deterministik — kode | LLM — Gemini |
|---|---|
| Skor deteksi dan kekritisan | Memutuskan jalur penelusuran berikutnya |
| Traversal graph | Menafsirkan teks bebas notifikasi |
| Angka, grafik, diagram, sitasi | Memilih blok dokumen, menyusun narasi |
| Penyusunan nilai untuk seluruh keluaran | Mengusulkan penekanan dan bentuk visual |

Model bahasa tidak pernah menyentuh angka. Salah memilih blok dokumen tidak fatal;
salah mengetik satu angka menghancurkan kepercayaan pada seluruh laporan.

Konsekuensi rancangan: nilai numerik mengalir dari sumber data ke keluaran tanpa
melewati model. Keluaran model diperlakukan sebagai **usulan**, bukan perintah —
lapisan penerima wajib menyaring nilai yang tidak dikenal, bukan mempercayainya.

**Cakupan.** Prinsip ini mengikat penuh pada **dokumen bukti** — memo, nota dinas,
dan laporan. Di sana nilai mengalir dari data ke keluaran tanpa pernah melewati
model, dan grafik dirender deterministik.

**Infografis dikecualikan sebagian**, dengan batas dan imbangan yang tegas. Ia
artefak ringkas untuk pembaca yang tidak akan membuka memo; ia **bukan catatan
resmi**, dan tidak pernah menjadi satu-satunya sumber sebuah angka.

| Tetap wajib | Boleh dari model |
|---|---|
| Seluruh teks, angka, label, dan sitasi disusun kode dari `Finding` | Penggambaran halaman: tata letak, bentuk visual, ilustrasi |
| Nilai yang dikirim ke penggambar bersifat verbatim | — |

Imbangan yang membuat pengecualian ini dapat dipertanggungjawabkan — ketiganya
wajib, bukan pilihan:

1. **Tidak ada nilai yang hanya dibawa oleh bentuk.** Setiap angka tertulis di
   sebelah grafiknya, sehingga kesalahan penggambaran tidak pernah menjadi
   kesalahan angka.
2. **Gerbang mutu memeriksa setiap string** pada halaman terhadap `Finding`.
   Teks yang tidak ditemukan di sumber membatalkan penerbitan.
3. **Memo tetap catatan resminya.** Angka yang dipakai untuk mengambil keputusan
   dirujuk dari memo, bukan dari infografis.

Batas ini disengaja: yang dipertaruhkan pada infografis adalah keterbacaan, dan
yang dipertaruhkan pada memo adalah kebenaran. Keduanya tidak ditukar.

### II. Setiap Klaim Dapat Ditelusuri

Setiap pernyataan dalam dokumen keluaran harus dapat dirunut ke dokumen sumber
atau ke simpul graph yang menjadi dasarnya. Sitasi bukan hiasan dan tidak pernah
masuk daftar fitur yang boleh dipotong.

Dokumen tanpa sitasi tidak boleh terbit.

### III. Agent Tidak Pernah Menulis Fakta

Agent tidak menulis langsung ke knowledge graph. Seluruh temuan masuk sebagai
kandidat berstatus `unreviewed` dan menunggu persetujuan manusia. Yang boleh
disetujui otomatis hanyalah kelas pemetaan yang sudah dinyatakan aman secara
eksplisit.

Sistem yang menulis kesimpulannya sendiri ke sumber kebenaran akan mengukuhkan
kesalahannya sendiri.

### IV. Ketidakpastian Dieskalasi, Bukan Ditebak

Bila dua kandidat penyebab teratas berselisih di bawah ambang keyakinan, sistem
menyatakan perlu putusan manusia dan menyajikan keduanya. Sistem tidak memilih
salah satu demi terlihat yakin.

Keyakinan palsu lebih berbahaya daripada ketidakpastian yang diakui.

### V. Modul Berkeputusan Tunggal, Bukan Kerangka Kerja

`scout → investigator → reporter → designer` adalah rantai; `curator` berjalan
ortogonal. Masing-masing memiliki tepat satu keputusan dan satu kontrak serah-terima.

| Modul | Keputusan miliknya |
|---|---|
| `scout` | Apa yang layak diselidiki |
| `investigator` | Langkah penelusuran berikutnya |
| `reporter` | Blok mana masuk dokumen dan urutannya |
| `designer` | Penekanan visual dan bentuk visual tiap blok |
| `curator` | Pemetaan mana yang layak diusulkan ke graph |

Batas antara `reporter` dan `designer` dijaga ketat: pemilihan blok tetap milik
`reporter`, dan `designer` menerimanya sebagai masukan. Dua modul tidak boleh
memiliki keputusan yang sama.

Jangan membangun kerangka kerja umum. Modul sederhana dengan kontrak jelas lebih
mudah dijelaskan ke penilai dan lebih mudah diperbaiki saat waktu menipis. Modul
kelima ditambahkan karena keputusan penyajian visual memang belum dimiliki modul
manapun — bukan karena sistem membutuhkan lapisan abstraksi baru.

### VI. Nol Data Klien (NON-NEGOTIABLE)

Repositori ini tidak memuat data klien satu baris pun, dan tidak menyebut nama
perusahaan, sektor nyata, atau lokasi asli — baik di kode, komentar, data, maupun
dokumen. Domain disebut "manufaktur FMCG multi-pabrik" saja. Skema penandaan aset
dirancang sendiri, tidak meniru format sistem manapun.

Seluruh data bersifat sintetis dan ditulis langsung ke tabel kanonik.

## Batasan Teknis

- **Runtime agent**: Google ADK, di-deploy ke Vertex AI Agent Engine.
- **Penyimpanan**: PostgreSQL 16 + Apache AGE + pgvector. Satu basis data untuk
  relasional, graph, dan vektor.
- **Bahasa**: Python 3.12, dikelola `uv`. Ruff dengan `line-length` 100.
- **Bahasa kode**: pengenal, docstring, dan komentar dalam bahasa Inggris.
- **Bahasa dokumen**: Indonesia untuk spesifikasi dan dokumen naratif. Berkas
  yang ditulis sebelum amandemen ini boleh tetap berbahasa Indonesia sampai
  disentuh; penerjemahan massal bukan pekerjaan yang mendesak.
- **`app/synthetic/`** adalah perkakas waktu-pengembangan dan tidak ikut ter-deploy.
- Keluaran dikirim sebagai ADK Artifacts.

## Alur Kerja

Proyek ini **brownfield**. Basis kode awal — model data, modul graph, lapisan
pelaporan — ditulis sebelum Spec Kit diterapkan. Konsekuensinya:

1. Spesifikasi mendokumentasikan komponen yang sudah berjalan **apa adanya**,
   ditandai jelas sebagai kondisi terpasang. Tidak ada klaim bahwa komponen
   tersebut lahir dari spesifikasi.
2. Komponen yang belum ditulis mengikuti urutan spec-first sepenuhnya:
   `specify → plan → tasks → implement`.
3. Perubahan pada komponen terpasang memutakhirkan spesifikasi lebih dulu.

Kejujuran urutan lebih bernilai daripada tampak rapi. Riwayat commit terbuka bagi
penilai dan harus cocok dengan yang dinyatakan.

## Governance

Constitution ini mengungguli seluruh dokumen lain dalam repositori. Prinsip
bertanda NON-NEGOTIABLE tidak boleh dilanggar demi tenggat; bila waktu menipis,
yang dipotong adalah cakupan fitur, bukan prinsip.

Urutan pemotongan cakupan yang sudah disepakati: deck PPTX dibuang lebih dulu,
lalu curator disederhanakan menjadi skrip batch, lalu infografis diringkas —
dan bila diringkas, yang dipertahankan adalah satu persona dengan blok paling
sedikit, bukan versi yang melonggarkan Prinsip I.
Tidak pernah dipotong: sitasi dokumen, jejak penalaran multi-hop, dan deploy
ke Agent Engine.

Setiap spesifikasi baru wajib menyebut prinsip mana yang mengikatnya. Penyimpangan
harus dicatat beserta alasannya di spesifikasi terkait, bukan diselesaikan diam-diam
di dalam kode.

### Riwayat amandemen

**1.2.0 — 2026-08-07.** Menetapkan cakupan Prinsip I untuk infografis.

- **Prinsip I** dipersempit cakupannya, bukan dilanggar. Mengikat penuh pada dokumen
  bukti; infografis dikecualikan pada tahap penggambaran, dengan tiga imbangan wajib:
  tidak ada nilai yang hanya dibawa bentuk, gerbang mutu memeriksa setiap string
  terhadap `Finding`, dan memo tetap catatan resmi. Prinsip tetap NON-NEGOTIABLE
  pada cakupannya.
- Alasan: keragaman tumpukan teknologi dinilai lebih bernilai daripada keseragaman
  jalur render, dan risikonya tertutup oleh ketiga imbangan di atas. Keputusan
  pemilik proyek, tercatat terbuka.

**1.1.0 — 2026-08-07.** Menyiapkan modul `designer`.

- **Prinsip I** dipertajam, bukan dilonggarkan. Ditambahkan batas eksplisit untuk
  keluaran visual: geometri yang membawa nilai tetap wajib deterministik, sementara
  penekanan, pemilihan bentuk, dan ilustrasi tanpa nilai boleh berasal dari model
  sebagai usulan. Ditambahkan aturan bahwa tidak ada nilai yang hanya dibawa oleh
  bentuk. Prinsip tetap NON-NEGOTIABLE.
- **Prinsip V** diperluas dari empat menjadi lima modul, dengan tabel keputusan
  eksplisit untuk mencegah `reporter` dan `designer` memiliki keputusan yang sama.
- **Batasan Teknis** mengubah bahasa kode menjadi Inggris; bahasa dokumen tetap
  Indonesia.

**Version**: 1.2.0 | **Ratified**: 2026-08-06 | **Last Amended**: 2026-08-07
