# Feature Specification: Curator — Kurasi Pengetahuan yang Masuk ke Graph

**Feature Branch**: `004-curator`

**Created**: 2026-08-11

**Status**: Retroaktif — ditulis setelah implementasi

**Input**: Agent kelima yang menilai kandidat fakta hasil investigasi dan memutuskan
mana yang aman diterima ke dalam pengetahuan tanpa persetujuan manusia, mana yang harus
dibawa ke manusia, dan mana yang ditolak.

## Konteks

⚠️ **Catatan kejujuran urutan.** Spec ini ditulis **setelah** Curator dibangun
(commit `834d099`). Ia mencatat perilaku sebagaimana ada dan menjadikannya dapat
diuji terhadap requirement, bukan memandu pembangunannya. Fitur 001 punya urutan
yang benar; fitur ini tidak, dan itu dituliskan alih-alih disamarkan.

Prinsip III konstitusi melarang agent menulis fakta ke graph. Konsekuensinya:
setiap temuan investigasi masuk sebagai klaim `unreviewed` dan menunggu. Tanpa
sesuatu yang mengurasinya, antrean itu tumbuh tanpa batas dan pengetahuan ARKA
membeku — kemampuan menemukan tidak pernah menjadi kemampuan mengingat.

Curator berjalan **ortogonal** terhadap rantai `Scout → Investigator → Reporter →
Designer`. Rantai itu menjawab pertanyaan yang ARKA angkat sendiri; Curator menjaga
apa yang boleh masuk ke pengetahuan yang dipakai menjawabnya.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Antrean tinjauan yang tidak tumbuh tanpa batas (Priority: P1)

Seorang knowledge owner membuka antrean kandidat fakta dan mendapati bahwa yang
menunggu keputusannya hanyalah yang memang menuntut penilaian manusia — bukan
ratusan klaim yang jelas kuat atau jelas lemah.

**Why this priority**: Persetujuan manusia yang tidak terkelola berubah menjadi
stempel karet. Antrean yang terlalu panjang dikosongkan dengan klik beruntun, dan
gerbang mutu yang dipasang Prinsip III justru hilang persis karena dipatuhi.

**Independent Test**: Beri lima kandidat dengan kekuatan bukti berbeda-beda, lalu
periksa bahwa yang sampai ke manusia hanya yang berada di antara kedua ambang.

**Acceptance Scenarios**:

1. **Given** klaim dengan tiga kutipan dari dokumen berwenang dan tanpa pembantah,
   **When** Curator berjalan, **Then** klaim itu diterima tanpa manusia, beserta
   catatan alasannya.
2. **Given** klaim dengan satu kutipan dari catatan teknisi, **When** Curator berjalan,
   **Then** klaim itu ditolak beserta alasannya — bukan didiamkan di antrean.
3. **Given** klaim yang skornya berada di antara kedua ambang, **When** Curator
   berjalan, **Then** klaim itu dieskalasi ke manusia.

### User Story 2 - Pertentangan selalu sampai ke manusia (Priority: P1)

Dua klaim menyatakan hal yang berlawanan tentang subjek yang sama. Salah satunya
didukung bukti jauh lebih banyak. Curator tetap membawa keduanya ke manusia.

**Why this priority**: Bukti yang banyak di satu sisi tidak menyelesaikan
perselisihan — ia hanya membuat salah satu pihak terlihat lebih ramai. Menerima
otomatis klaim yang dibantah adalah cara paling cepat menanamkan kesalahan yang
akan dikutip berkali-kali sesudahnya.

**Independent Test**: Beri klaim berskor tinggi yang dibantah klaim lain, lalu
periksa bahwa hasilnya eskalasi, bukan persetujuan.

**Acceptance Scenarios**:

1. **Given** klaim berskor di atas ambang persetujuan otomatis yang dibantah klaim
   lain, **When** Curator memutuskan, **Then** hasilnya eskalasi.
2. **Given** model meminta menyetujui klaim yang dibantah, **When** permintaan itu
   dijalankan, **Then** kode menolaknya — bukan prompt yang melarangnya.

### User Story 3 - Keputusan yang dapat dipertanggungjawabkan (Priority: P2)

Seorang auditor menanyakan kenapa sebuah fakta ada di dalam graph, dan memperoleh
skor, komponen penyusunnya, keputusannya, dan alasannya.

**Why this priority**: Pengetahuan yang diterima otomatis hanya dapat dipercaya bila
jalan masuknya dapat ditelusuri. Tanpa jejak, kurasi otomatis adalah kepercayaan buta
yang dipasang di lapisan paling dalam.

**Independent Test**: Setujui satu kandidat, lalu baca kembali catatan tinjauannya.

**Acceptance Scenarios**:

1. **Given** kandidat yang sudah diputuskan, **When** catatannya dibaca, **Then** ia
   memuat skor, keputusan, dan alasan dalam kalimat yang dapat dibaca manusia.

### Edge Cases

- Kandidat tanpa satu pun kutipan → ditolak; tidak ada jalur menerima klaim tanpa dasar.
- Jenis dokumen yang tidak dikenal → diberi kewenangan terendah, bukan diabaikan.
- Antrean kosong → Curator melaporkan tidak ada yang perlu diputuskan, bukan gagal.
- Model meminta keputusan atas kandidat yang tidak ada → ditolak tool.

## Requirements *(mandatory)*

### Penilaian

- **FR-001**: Sistem MUST menghitung kekuatan tiap kandidat fakta secara deterministik
  dari jumlah kutipan, keyakinan ekstraksi, kewenangan jenis dokumen, dan ada tidaknya
  pembantah. Model MUST TIDAK menghitung atau mengubah nilai ini.
- **FR-002**: Bobot dan ambang MUST diterbitkan sebagai kebijakan; yang disetel ketika
  hasilnya tidak sesuai harapan adalah datanya, bukan keduanya.
- **FR-003**: Sistem MUST mengembalikan komponen penyusun skor, bukan hanya totalnya.

### Keputusan

- **FR-004**: Sistem MUST menyetujui otomatis hanya kandidat di atas ambang aman.
- **FR-005**: Sistem MUST menolak kandidat di bawah ambang terlalu lemah, beserta alasan.
- **FR-006**: Sistem MUST mengeskalasi kandidat di antara kedua ambang ke manusia.
- **FR-007**: Kandidat yang dibantah klaim lain tentang subjek yang sama MUST
  dieskalasi berapa pun skornya, dan MUST TIDAK dapat disetujui lewat jalur otomatis.
- **FR-008**: Larangan pada FR-007 MUST ditegakkan di kode, bukan di prompt.
- **FR-009**: Model MUST boleh lebih berhati-hati daripada ambang, dan MUST TIDAK
  boleh lebih longgar.

### Jejak

- **FR-010**: Setiap keputusan MUST tercatat beserta skor dan alasannya.
- **FR-011**: Yang ditulis Curator MUST berupa keputusan tentang fakta, bukan fakta —
  Prinsip III tetap berlaku penuh terhadapnya.

## Success Criteria *(mandatory)*

- **SC-001**: Dari sekumpulan kandidat dengan kekuatan beragam, yang sampai ke manusia
  hanya yang berada di wilayah ragu — terukur, bukan diperkirakan.
- **SC-002**: Nol kandidat yang dibantah pernah disetujui otomatis, termasuk ketika
  model memintanya.
- **SC-003**: Setiap fakta yang masuk ke graph lewat jalur ini dapat ditelusuri ke
  skor dan alasan yang menerimanya.

## Assumptions

- Kandidat fakta sudah ada sebagai klaim `unreviewed` beserta kutipannya — dihasilkan
  lapisan investigasi, bukan oleh fitur ini.
- Ambang 0,75 dan 0,40 adalah kebijakan yang diterbitkan, sejajar dengan ambang deteksi
  0,65 / 0,50 pada fitur 001.
- Manusia tetap memutuskan yang dieskalasi; fitur ini tidak menyediakan antarmuka
  peninjauannya, hanya antreannya.

## Key Entities

- **Kandidat klaim**: Fakta yang diusulkan, beserta kutipan pendukung dan penanda
  apakah ada klaim yang membantahnya.
- **Skor klaim**: Empat komponen beserta totalnya.
- **Vonis**: Keputusan, skor yang mendasarinya, dan alasan yang dapat dibaca manusia.

## Ketergantungan

- Fitur 001 — Prinsip III, kontrak klaim `unreviewed`, dan pola ambang yang diterbitkan.

## Cakupan implementasi

| Requirement | Wujudnya | Diuji di |
|---|---|---|
| FR-001, FR-002, FR-003 | `app/curation/scoring.py` | `tests/test_curation_scoring.py` |
| FR-004 … FR-007 | `putuskan()` di `app/curation/scoring.py` | `tests/test_curation_scoring.py` |
| FR-008, FR-009 | `putuskan_kandidat` di `app/agents/curator.py` | `tests/test_curator_agent.py` |
| FR-010, FR-011 | `catat_keputusan` di `app/curation/repository.py` | `tests/test_curator_agent.py` |
