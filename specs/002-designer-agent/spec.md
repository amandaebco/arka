# Feature Specification: Modul `designer` — Penyajian Visual Temuan

**Feature Branch**: `002-designer-agent`

**Created**: 2026-08-07

**Status**: Draft

**Input**: Modul kelima yang mengubah `Finding` menjadi infografis satu halaman.
`reporter` sudah memutuskan blok mana yang masuk dokumen; `designer` memutuskan
bagaimana blok-blok itu disajikan secara visual — mana yang mendominasi halaman
dan bentuk visual apa yang dipakai masing-masing. Seluruh angka, teks, dan geometri
yang membawa nilai tetap dirender deterministik.

## Prinsip yang Mengikat

| Prinsip | Cara spesifikasi ini mematuhinya |
|---|---|
| **I. Angka Deterministik** (NON-NEGOTIABLE) | Infografis berada di dalam pengecualian yang ditetapkan Constitution 1.2.0. Teks, angka, dan sitasi tetap disusun kode dari `Finding` dan dikirim verbatim ke penggambar; yang berasal dari model hanya penggambaran halaman. Ketiga imbangan wajib berlaku penuh — lihat FR-006, FR-007, dan FR-011. |
| **II. Setiap Klaim Dapat Ditelusuri** | Infografis memuat rujukan dokumen untuk klaim yang membawanya; tidak menggantikan memo sebagai dokumen bukti. |
| **IV. Ketidakpastian Dieskalasi** | Tingkat keyakinan dan penanda eskalasi wajib tampil; blok yang datanya tidak ada tidak pernah dirender sebagai kartu kosong. |
| **V. Modul Berkeputusan Tunggal** | `designer` memiliki tepat satu keputusan: penekanan dan bentuk visual. Pemilihan blok tetap milik `reporter` dan diterima sebagai masukan. |
| **VI. Nol Data Klien** (NON-NEGOTIABLE) | Aset desain dan contoh seluruhnya sintetis. |

**Penyimpangan tercatat:** tidak ada. Constitution 1.1.0 menambahkan modul kelima,
dan 1.2.0 menetapkan cakupan Prinsip I beserta pengecualian infografis. Spesifikasi
ini berada di dalam prinsip, bukan menyimpang darinya.

**Konsekuensi yang harus disadari.** Penggambaran oleh model membawa dua sifat yang
tidak dimiliki jalur deterministik, dan keduanya diterima secara sadar:

1. **Keluaran tidak identik antar-penerbitan.** `Finding` yang sama dapat
   menghasilkan halaman yang berbeda susunan piksel dan pilihan gambarnya. Yang
   dijamin identik adalah nilainya, bukan rupanya.
2. **Waktu terbit dalam hitungan puluhan detik**, sehingga infografis tidak dapat
   diperagakan sebagai proses langsung dalam anggaran waktu demo.

Imbangan pada FR-006, FR-007, dan FR-011 ada untuk menutup risiko yang timbul dari
sifat pertama. Sifat kedua adalah batasan operasional, bukan cacat.

## Catatan Brownfield

Sebagian kapabilitas berasal dari purwarupa terpisah yang dibangun lebih dulu di luar
repositori ini. Statusnya dinyatakan terbuka:

| Komponen | Status | Keterangan |
|---|---|---|
| Pustaka pengetahuan desain (44 aset) | **Terpasang di luar** | Divalidasi, 108 pengujian deterministik. Dipindahkan, bukan ditulis ulang |
| Pemilihan blok berdasarkan ketersediaan data | **Terpasang di luar** | Sejajar dengan `Blok.tersedia` yang sudah ada di sini |
| Penyusun prompt deterministik | **Terpasang di luar** | Pindah apa adanya; masukannya berubah dari markdown ke `Finding` |
| Penggambar halaman (model gambar) | **Terpasang di luar** | Pindah apa adanya |
| Agent `designer` | **Belum ada** | Mengikuti spec-first penuh |
| Rubrik penilai untuk infografis | **Belum ada** | Memperluas `penilai` yang sudah ada |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Temuan menjadi satu halaman yang bisa dibaca sekilas (Priority: P1)

Seorang manajer menerima hasil investigasi. Ia tidak akan membaca memo tiga halaman
sebelum rapat. Ia membuka satu halaman yang menyajikan kondisi, penyebab teratas,
preseden, dan tindakan prioritas — dengan angka yang sama persis seperti di memo.

**Why this priority**: Memo menjawab "apa buktinya"; infografis menjawab "apa yang
perlu saya putuskan". Tanpa ini, temuan ARKA hanya terbaca oleh yang sempat membaca.

**Independent Test**: Muat satu `Finding` jalur emas, terbitkan infografis, dan
bandingkan setiap angka di dalamnya dengan memo dari `Finding` yang sama.

**Acceptance Scenarios**:

1. **Given** `Finding` dengan kandidat penyebab berskor dan preseden lintas pabrik,
   **When** infografis diterbitkan, **Then** halaman memuat kandidat teratas,
   preseden, dan rekomendasi dengan nilai numerik identik dengan memo.
2. **Given** `Finding` yang sama diterbitkan dua kali, **When** keduanya dibandingkan,
   **Then** seluruh teks dan geometri bernilai identik.

### User Story 2 — Halaman menyesuaikan data, bukan template tetap (Priority: P1)

Dua temuan berbeda kekayaan datanya. Yang satu memiliki preseden, kekritisan
sparepart, dan rantai kausal lengkap. Yang lain baru memiliki gejala dan satu
kandidat. Keduanya menghasilkan halaman yang berbeda susunannya — bukan satu
template dengan bagian kosong.

**Why this priority**: Kartu kosong menyiratkan data yang tidak ada, dan itu bentuk
kebohongan yang paling mudah lolos. Ini juga pembeda utama modul ini terhadap
pembangkit infografis biasa.

**Independent Test**: Terbitkan dari dua `Finding` — satu lengkap, satu minimal —
dan periksa bahwa blok tanpa data tidak muncul sama sekali.

**Acceptance Scenarios**:

1. **Given** `Finding` tanpa data sparepart, **When** infografis diterbitkan,
   **Then** blok kekritisan sparepart tidak muncul dalam bentuk apa pun.
2. **Given** `Finding` tanpa preseden, **When** infografis diterbitkan, **Then**
   halaman tetap utuh secara komposisi tanpa ruang kosong menganga.

### User Story 3 — Ketidakpastian tetap terlihat (Priority: P1)

Temuan dengan keyakinan rendah tidak boleh menghasilkan halaman yang terlihat
sama yakinnya dengan temuan berkeyakinan tinggi.

**Why this priority**: Mengikat Prinsip IV. Desain yang terlalu rapi pada temuan
yang lemah adalah cara paling halus untuk menyesatkan pembaca.

**Independent Test**: Terbitkan dari `Finding` dengan `keyakinan="rendah"` dan
`perlu_eskalasi=True`, lalu periksa penandaannya.

**Acceptance Scenarios**:

1. **Given** `Finding` berkeyakinan rendah, **When** infografis diterbitkan,
   **Then** tingkat keyakinan tampil sebagai tiga tingkat baku, tidak pernah
   sebagai persentase.
2. **Given** `Finding` dengan `perlu_eskalasi` bernilai benar, **When** infografis
   diterbitkan, **Then** penanda eskalasi tampil beserta kedua kandidat teratas.

### User Story 4 — Penilai menolak halaman yang cacat (Priority: P2)

Halaman yang kehilangan blok, kehilangan titik fokus, atau memuat teks yang
tidak berasal dari `Finding` dikembalikan untuk diperbaiki, bukan diterbitkan.

**Why this priority**: Gerbang mutu adalah pembeda yang tidak dimiliki pembangkit
infografis manapun yang ditinjau.

**Independent Test**: Suntikkan halaman cacat buatan dan periksa penilai menolaknya.

**Acceptance Scenarios**:

1. **Given** halaman yang kehilangan satu blok yang diminta, **When** penilai
   memeriksa, **Then** penilai menandainya dan `designer` menyusun ulang.
2. **Given** halaman yang lolos seluruh pemeriksaan, **When** penilai memeriksa,
   **Then** halaman diterbitkan tanpa putaran tambahan.

### Edge Cases

- `Finding` tanpa satu pun kandidat penyebab — halaman tetap terbit, memuat gejala,
  jejak penalaran, dan pernyataan bahwa penyebab belum dapat disimpulkan.
- Blok yang datanya melebihi kapasitas halaman — blok berpenekanan terendah
  dipangkas lebih dulu; blok wajib tidak pernah dipangkas.
- Ilustrasi gagal diterbitkan — halaman tetap terbit tanpa ilustrasi, karena
  ilustrasi tidak membawa nilai.
- Model mengusulkan bentuk visual yang datanya tidak memenuhi syarat — usulan
  ditolak lapisan penerima, blok dirender sebagai teks biasa.

## Requirements *(mandatory)*

### Functional Requirements

**Keputusan dan batas modul**

- **FR-001**: `designer` MUST menerima daftar blok terpilih beserta urutannya dari
  `reporter`, dan MUST NOT mengubah pemilihan maupun urutan itu.
- **FR-002**: `designer` MUST menghasilkan spesifikasi penyajian yang menyebut
  penekanan tiap blok dan bentuk visual tiap blok, dinyatakan sebagai pengenal dari
  pustaka pengetahuan desain.
- **FR-003**: Sistem MUST menolak spesifikasi penyajian yang menyebut pengenal di
  luar pustaka, blok di luar yang dipilih `reporter`, atau lebih dari satu blok
  berpenekanan dominan.

**Kesetiaan nilai**

- **FR-004**: Seluruh teks, angka, dan label yang dikirim ke penggambar MUST disusun
  kode dari `Finding` secara verbatim, tanpa melewati model bahasa.
- **FR-005**: Sistem MUST NOT meminta penggambar menghitung, membulatkan, menyimpulkan,
  atau menerjemahkan nilai apa pun.
- **FR-006**: Setiap nilai yang disajikan dalam bentuk visual MUST juga tertulis
  sebagai angka di sebelahnya, sehingga kesalahan penggambaran tidak pernah menjadi
  kesalahan angka. *(Imbangan 1, Constitution 1.2.0)*
- **FR-007**: Infografis MUST memuat penanda bahwa memo adalah catatan resmi untuk
  nilai yang dipakai mengambil keputusan. *(Imbangan 3, Constitution 1.2.0)*
- **FR-008**: Sistem MUST NOT menampilkan tingkat keyakinan sebagai persentase.

**Pemilihan blok berdasarkan data**

- **FR-009**: Setiap blok MUST menyatakan prasyarat datanya, dan MUST NOT dirender
  bila prasyaratnya tidak terpenuhi.
- **FR-010**: Blok yang dinyatakan wajib MUST selalu dirender, termasuk saat
  isinya adalah pernyataan bahwa data belum tersedia.
- **FR-011**: Bila jumlah blok melampaui kapasitas halaman, sistem MUST memangkas
  dari penekanan terendah dan MUST NOT memangkas blok wajib.

**Gerbang mutu**

- **FR-012**: Penilai MUST memeriksa **setiap string** yang tampil pada halaman
  terhadap `Finding`. Teks yang tidak ditemukan di sumber MUST membatalkan
  penerbitan. *(Imbangan 2, Constitution 1.2.0)*
- **FR-013**: Penilai MUST memeriksa kelengkapan blok, kesesuaian penekanan
  terhadap spesifikasi penyajian, dan keterbacaan halaman.
- **FR-014**: Loop `designer ↔ penilai` MUST berhenti pada maksimum tiga putaran.
- **FR-015**: Bila target mutu tidak tercapai, sistem MUST menerbitkan hasil
  berskor tertinggi beserta laporan penilaiannya, bukan menahan keluaran.

**Penerbitan**

- **FR-016**: Infografis MUST diterbitkan sebagai ADK Artifact, sejajar dengan memo.
- **FR-017**: Nilai numerik pada infografis MUST identik dengan memo dari `Finding`
  yang sama.
- **FR-018**: Sistem MUST menyimpan spesifikasi penyajian, hasil penilaian, dan
  berkas keluaran tiap putaran, agar halaman terbit dapat dipertanggungjawabkan
  meski penggambarannya tidak dapat diulang persis.

### Key Entities

- **SpesifikasiPenyajian**: Keluaran `designer`. Memuat penekanan per blok, bentuk
  visual per blok, dan pemetaan nilai status ke warna semantik. Tidak memuat satu
  pun teks isi — seluruhnya berupa pengenal.
- **PustakaDesain**: Kumpulan aset yang menyatakan tata letak, tipografi, sistem
  warna, sistem ikon, bentuk visual, dan batas desain. Divalidasi saat dimuat;
  pengenal yang tidak dikenal ditolak.
- **BentukVisual**: Satu cara menyajikan blok, beserta prasyarat data dan aturan
  penggambarannya. Bentuk yang prasyaratnya tidak terpenuhi tidak boleh dipakai.
- **PenilaianHalaman**: Skor per dimensi, temuan, dan keputusan terima atau ulangi.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Seluruh nilai numerik identik antara infografis dan memo untuk
  `Finding` yang sama — tanpa kecuali.
- **SC-002**: Dua `Finding` dengan kekayaan data berbeda menghasilkan susunan blok
  yang berbeda, dan tidak satu pun blok terbit tanpa isi.
- **SC-003**: `Finding` yang sama diterbitkan dua kali menghasilkan **nilai** yang
  identik. Rupa halaman boleh berbeda — itu sifat penggambaran oleh model, bukan cacat.
- **SC-004**: Temuan berkeyakinan rendah selalu menampilkan tingkat keyakinan dan
  penanda eskalasi.
- **SC-005**: Tidak ada teks pada halaman yang tidak dapat ditemukan di `Finding` —
  diperiksa penilai pada setiap putaran, bukan hanya di akhir.
- **SC-006**: Setiap nilai yang tampil dalam bentuk visual juga tampil sebagai angka.
- **SC-007**: Halaman terbit dalam waktu yang memungkinkan pemicuannya di awal
  peragaan dan pengungkapannya di akhir, dalam satu sesi yang sama.

## Assumptions

- `reporter` sudah menetapkan blok dan urutannya sebelum `designer` dipanggil.
- Pustaka pengetahuan desain dipindahkan dari purwarupa dalam keadaan tervalidasi;
  aset yang tidak relevan dengan keluaran statis tidak ikut dipindahkan.
- Dua persona pembaca dipakai: `engineer` dan `reliability_manager`. Struktur pustaka
  memungkinkan penambahan persona tanpa perubahan skema. Bila cakupan dipotong, yang
  dipertahankan satu persona — bukan pelonggaran imbangan Prinsip I.
- Penggambaran memakai penyedia model gambar di luar Google. Ini dipilih sadar untuk
  memperluas keragaman tumpukan teknologi, dan menjadi satu-satunya jalur di ARKA
  yang mengirim data ke luar. Isinya terbatas pada nilai yang sudah ada di `Finding`.
- Keluaran berupa berkas gambar. Tidak ada keluaran PDF untuk infografis; memo dan
  nota dinas tetap memikul peran dokumen cetak.
