# Feature Specification: ARKA — Asset Reliability Knowledge Agent

**Feature Branch**: `001-arka-knowledge-agent`

**Created**: 2026-08-06

**Status**: Draft

**Input**: Agent otonom yang menyelidiki akar masalah kegagalan mesin di manufaktur
FMCG multi-pabrik. Berjalan di atas knowledge graph, menelusuri hubungan antara aset,
riwayat perbaikan, dokumen inspeksi, dan rantai pasok sparepart untuk menemukan
penyebab yang tidak terlihat di sistem manapun, lalu menyusunnya menjadi dokumen yang
setiap klaimnya bisa ditelusuri ke dokumen sumbernya.

## Catatan Brownfield

Spesifikasi ini ditulis atas proyek yang sudah berjalan. Status tiap komponen
dinyatakan terbuka, mengikuti prinsip Alur Kerja pada Constitution:

| Komponen | Status | Keterangan |
|---|---|---|
| Model data & migrasi | **Terpasang** | Ditulis sebelum Spec Kit diterapkan |
| Modul graph (proyeksi, neighborhood, competency) | **Terpasang** | Idem |
| Lapisan pelaporan (`Finding` → blok → dokumen) | **Terpasang** | Idem |
| Agent `reporter` | **Terpasang** | Idem |
| Data sintetis | **Sebagian** | Generator ada, belum sesuai syarat jalur emas |
| Agent `investigator` | **Belum ada** | Mengikuti spec-first penuh |
| Agent `scout` | **Belum ada** | Mengikuti spec-first penuh |
| Agent `curator` | **Belum ada** | Mengikuti spec-first penuh |

Komponen berstatus Terpasang didokumentasikan **apa adanya**. Tidak ada klaim bahwa
komponen tersebut dihasilkan dari spesifikasi ini.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Menemukan preseden lintas pabrik (Priority: P1)

Seorang reliability engineer menghadapi kegagalan berulang pada satu mesin. Ia
bertanya kepada ARKA tentang aset tersebut. ARKA menelusuri graph, menemukan bahwa
kegagalan dengan pola gejala serupa pernah terjadi pada model mesin yang sama di
pabrik lain, dan bahwa salah satunya sudah pernah diselesaikan dengan tindakan yang
tercatat di laporan inspeksi. Engineer menerima jawaban beserta rujukan dokumennya.

**Why this priority**: Inilah nilai inti ARKA. Pengetahuan penyelesaian sudah ada di
organisasi tetapi terkubur di pabrik lain, sehingga kegagalan yang sama dibayar
berulang kali dari nol. Tanpa cerita ini, sisa sistem kehilangan alasan keberadaannya.

**Independent Test**: Dapat diuji penuh dengan memuat data sintetis, menanyakan satu
aset yang gejalanya sengaja dirancang menyerupai kasus historis di pabrik lain, dan
memeriksa bahwa preseden beserta penyelesaiannya muncul dengan sitasi yang benar.

**Acceptance Scenarios**:

1. **Given** graph memuat kegagalan historis pada model mesin yang sama di sekurangnya
   lima pabrik, **When** engineer menanyakan aset dengan gejala serupa,
   **Then** ARKA mengembalikan preseden dari pabrik lain beserta tindakan
   penyelesaian yang tercatat dan rujukan dokumennya.
2. **Given** kasus historis yang penyelesaiannya terbukti berhasil,
   **When** ARKA menyusun temuan, **Then** tindakan tersebut muncul sebagai
   rekomendasi berprioritas tertinggi.
3. **Given** aset tanpa preseden yang melewati ambang kemiripan,
   **When** engineer bertanya, **Then** ARKA menyatakan tidak menemukan preseden
   dan tidak mengarang kemiripan.

---

### User Story 2 - Dokumen yang setiap klaimnya tertelusur (Priority: P1)

Engineer meminta hasil investigasi dalam bentuk dokumen untuk diteruskan ke unit lain.
ARKA menerbitkan dokumen berisi angka, tabel, dan daftar dokumen sumber. Pembaca yang
skeptis dapat memeriksa setiap klaim sampai ke dokumen asalnya.

**Why this priority**: Temuan yang tidak dapat diperiksa tidak akan dipakai untuk
mengambil keputusan. Keterlacakan inilah yang membedakan ARKA dari peringkas teks.

**Independent Test**: Dapat diuji tanpa graph, dengan memberikan objek temuan langsung
lalu memeriksa keluaran memuat seluruh sitasi dan angka yang benar.

**Acceptance Scenarios**:

1. **Given** temuan dengan sitasi, **When** dokumen diterbitkan,
   **Then** seluruh dokumen sumber tercantum lengkap dengan penunjuk bagiannya.
2. **Given** narasi model yang memuat angka keliru, **When** dokumen diterbitkan,
   **Then** angka yang tampil tetap berasal dari data, bukan dari narasi.
3. **Given** satu temuan yang sama, **When** diterbitkan sebagai memo, nota dinas,
   dan laporan, **Then** seluruh nilai numerik dan sitasi identik di ketiganya.
4. **Given** temuan tanpa sitasi sama sekali, **When** penerbitan diminta,
   **Then** sistem menolak menerbitkan dokumen.

---

### User Story 3 - Ketidakpastian yang diakui (Priority: P2)

Dua penyebab sama-sama masuk akal dan menuntut tindakan berbeda. ARKA tidak memilih
salah satu. Ia menandai temuan sebagai perlu putusan manusia dan menyajikan keduanya
beserta dasar masing-masing.

**Why this priority**: Menjaga kepercayaan. Sistem yang selalu terdengar yakin akan
ditinggalkan begitu satu kesalahan percaya-diri terbongkar.

**Independent Test**: Dapat diuji dengan kasus yang dirancang menghasilkan dua kandidat
berselisih di bawah ambang, lalu memeriksa penandaan eskalasi muncul.

**Acceptance Scenarios**:

1. **Given** dua kandidat teratas berselisih di bawah ambang keyakinan,
   **When** temuan disusun, **Then** temuan ditandai perlu eskalasi dan kedua
   kandidat tersaji beserta alasan eskalasinya.
2. **Given** temuan berstatus eskalasi, **When** dokumen diterbitkan,
   **Then** penandaan tersebut tampil menonjol sebelum isi.

---

### User Story 4 - Kekritisan sparepart yang tak terlihat di master data (Priority: P2)

ARKA menghitung kekritisan sparepart dari kondisi nyata — peluang kegagalan, akibatnya,
dan kerapuhan pasokan — lalu membandingkannya dengan nilai statis di master data.
Selisih terbesar menunjuk komponen yang selama ini dinilai terlalu rendah.

**Why this priority**: Menghubungkan keandalan aset dengan rantai pasok. Nilainya ada
pada selisih, bukan pada angka kekritisan itu sendiri.

**Independent Test**: Dapat diuji dengan sparepart bervendor tunggal dan lead time
panjang yang master data menilainya rendah, lalu memeriksa selisih tampil menonjol.

**Acceptance Scenarios**:

1. **Given** sparepart dengan vendor tunggal dan lead time panjang yang dipakai
   banyak pabrik, **When** kekritisan dihitung, **Then** nilainya melampaui
   kekritisan statis dan selisihnya tersaji.
2. **Given** daftar sparepart, **When** disajikan, **Then** urutannya mengikuti
   selisih terbesar lebih dulu.

---

### User Story 5 - Temuan menunggu persetujuan (Priority: P3)

Temuan ARKA masuk sebagai kandidat berstatus belum ditinjau. Manusia menyetujui atau
menolak. Hanya kelas pemetaan yang dinyatakan aman yang boleh disetujui otomatis.

**Why this priority**: Menjaga graph tetap menjadi sumber kebenaran. Penting untuk
tata kelola, tetapi tidak diperlukan agar cerita utama dapat diperagakan.

**Independent Test**: Dapat diuji dengan memeriksa temuan baru tidak pernah mengubah
fakta terverifikasi tanpa melewati persetujuan.

**Acceptance Scenarios**:

1. **Given** temuan baru, **When** disimpan, **Then** statusnya belum ditinjau dan
   fakta terverifikasi tidak berubah.

---

### Edge Cases

- Aset yang ditanyakan tidak ada di graph, atau tag-nya salah ketik.
- Kegagalan tanpa satu pun preseden melewati ambang kemiripan.
- Dokumen sumber ada tetapi tidak memuat petikan yang relevan.
- Penelusuran menemukan terlalu banyak kandidat sehingga tidak ada yang menonjol.
- Sekitar 8% work order tidak tertaut ke equipment manapun — kotor sejak asalnya.
- Katalog pemetaan memuat typo ala OCR dan tag ambigu.
- Model bahasa mengembalikan pilihan blok yang tidak dikenal atau blok kosong.
- Model bahasa gagal merespons, waktu habis, atau tersaring filter keamanan.
- Peramban untuk render PDF tidak tersedia di lingkungan penerbitan.

## Requirements *(mandatory)*

### Functional Requirements

**Penelusuran dan deteksi**

- **FR-001**: Sistem MUST menelusuri hubungan antar aset, komponen, kegagalan
  historis, dokumen, dan sparepart secara multi-hop.
- **FR-002**: Sistem MUST memberi skor kemiripan antara kegagalan yang sedang
  diselidiki dan kegagalan historis, dihitung secara deterministik.
- **FR-003**: Sistem MUST mengabaikan kandidat di bawah ambang bawah, melaporkan
  kandidat di atas ambang atas, dan mengeskalasi bila dua kandidat teratas
  berselisih di bawah ambang selisih.
- **FR-004**: Sistem MUST merekam jejak penelusuran langkah demi langkah, memuat
  apa yang ditelusuri dan apa yang ditemukan.
- **FR-005**: Sistem MUST membatasi kedalaman dan luas penelusuran agar
  investigasi selalu berakhir.

**Kekritisan sparepart**

- **FR-006**: Sistem MUST menghitung kekritisan sparepart dari peluang kegagalan,
  akibat, dan risiko pasokan secara deterministik.
- **FR-007**: Sistem MUST menyajikan selisih terhadap kekritisan statis di master data.

**Keterlacakan**

- **FR-008**: Setiap kandidat penyebab dan setiap preseden MUST membawa rujukan ke
  dokumen sumber bila dokumen pendukungnya ada.
- **FR-009**: Sistem MUST menolak menerbitkan dokumen yang tidak memuat satu pun sitasi.
- **FR-010**: Nilai numerik dalam dokumen MUST berasal langsung dari data, tidak
  melewati model bahasa.

**Penerbitan dokumen** *(terpasang)*

- **FR-011**: Sistem MUST menerbitkan hasil investigasi sebagai memo, nota dinas,
  atau laporan, dengan isi dan nilai yang identik antar bentuk.
- **FR-012**: Sistem MUST memperlakukan pilihan blok dan urutan dari model bahasa
  sebagai usulan — menyaring id yang tidak dikenal dan blok tanpa data.
- **FR-013**: Sistem MUST menyertakan blok ringkasan dan blok dokumen sumber pada
  setiap dokumen, terlepas dari pilihan model.
- **FR-014**: Sistem MUST menyimpan dokumen sebagai artifact sesi.
- **FR-015**: Sistem MUST menggagalkan penerbitan secara terang-terangan bila
  perender utama tidak tersedia, dan MUST TIDAK menyerahkan bentuk alternatif
  sebagai pengganti diam-diam.

  *Diamandemen 10 Agt 2026.* Rumusan semula mensyaratkan bentuk alternatif.
  Implementasi mengambil arah sebaliknya pada 7 Agt: dokumen bukti dipakai
  mengambil keputusan perawatan, dan berkas HTML yang tampak resmi tetapi bukan
  bentuk resminya lebih berbahaya daripada kegagalan yang terlihat. Sejak
  Chromium dipanggang ke dalam image, PDF tersedia di semua lingkungan, sehingga
  jalur mundur itu tidak lagi punya alasan keberadaan. HTML tetap ada sebagai
  bentuk kerja internal — lihat `scripts/render_contoh.py`.
- **FR-016**: Sistem MUST menanyakan kelengkapan surat kepada pengguna alih-alih
  mengarang nama, jabatan, atau nomor surat.

**Tata kelola pengetahuan**

- **FR-017**: Sistem MUST menyimpan temuan sebagai kandidat belum ditinjau dan
  tidak pernah menulis langsung ke fakta terverifikasi.
- **FR-018**: Sistem MUST membatasi persetujuan otomatis hanya pada kelas pemetaan
  yang dinyatakan aman secara eksplisit.

**Ketahanan**

- **FR-019**: Kegagalan satu sumber data MUST tidak menggagalkan seluruh investigasi;
  bagian yang gagal dilaporkan kosong dan ditandai.
- **FR-020**: Sistem MUST menangani data kotor — tag salah ketik, tautan hilang,
  pemetaan ambigu — tanpa berhenti.

### Key Entities

- **Equipment**: Satu unit mesin di satu pabrik, memiliki model dan tag unik.
- **Component**: Bagian dari equipment, jenjang tempat kecocokan kegagalan dinilai.
- **FailureEvent**: Satu kejadian kegagalan historis beserta gejala, penanganan,
  dan lama berhenti.
- **Cause**: Penyebab yang dikenal, dapat tertaut ke banyak kejadian.
- **Document**: Laporan inspeksi, catatan teknisi, manual, atau FMEA — dasar sitasi.
- **Part**: Sparepart, terhubung ke komponen dan ke pemasoknya.
- **Finding**: Keluaran investigator — kandidat penyebab berskor, preseden, rantai
  kausal, kekritisan sparepart, jejak penalaran, rekomendasi, dan sitasi. Menjadi
  satu-satunya kontrak masukan bagi penerbitan dokumen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Untuk kasus jalur emas, ARKA mengembalikan preseden dari sekurangnya
  tiga pabrik berbeda yang tidak disebut dalam pertanyaan pengguna.
- **SC-002**: Setiap klaim substantif dalam dokumen terbit dapat dirunut ke dokumen
  sumber atau simpul graph — tanpa kecuali.
- **SC-003**: Seluruh nilai numerik identik antara memo, nota dinas, dan laporan
  untuk temuan yang sama.
- **SC-004**: Kasus yang dirancang ambigu selalu memicu penandaan eskalasi, tidak
  pernah menghasilkan satu kesimpulan tunggal.
- **SC-005**: Investigasi jalur emas selesai tanpa campur tangan manusia dari
  pertanyaan sampai dokumen terbit.
- **SC-006**: Jejak penalaran memuat sekurangnya satu langkah yang menyeberangi
  batas pabrik — bukti penemuan lintas-pabrik memang terjadi, bukan kebetulan.
- **SC-007**: Sistem berjalan di Vertex AI Agent Engine, bukan hanya di lingkungan lokal.

## Assumptions

- Seluruh data bersifat sintetis dan dirancang memuat jalur emas: armada seragam di
  sekurangnya lima pabrik, pola kegagalan berulang dengan satu penyelesaian tercatat,
  dan sparepart bervendor tunggal yang master data menilainya rendah.
- Pengguna adalah reliability engineer yang memahami istilah teknis pemeliharaan.
- Dokumen sumber sudah tersedia dalam bentuk yang dapat dikutip; digitalisasi
  dokumen di luar cakupan.
- Ambang skor ditetapkan dari pertimbangan rancangan, bukan dari kalibrasi terhadap
  data lapangan nyata.
- Bobot rumus skor deteksi dan kekritisan bersifat tetap pada versi ini; pembelajaran
  bobot dari umpan balik di luar cakupan.
- Antarmuka percakapan adalah pintu masuk ke investigator, bukan identitas sistem.
  ARKA dinilai sebagai agent otonom, bukan sebagai chatbot.
- Persetujuan manusia atas kandidat temuan dijalankan lewat proses sederhana;
  antarmuka peninjauan penuh di luar cakupan versi ini.
