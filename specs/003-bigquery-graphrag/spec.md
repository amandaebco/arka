# Feature Specification: Lapisan Retrieval Produksi — Graph, Vektor, dan Tanya-Jawab

**Feature Branch**: `003-bigquery-graphrag`

**Created**: 2026-08-11

**Status**: Draft

**Input**: Lapisan retrieval untuk produksi: knowledge graph berjalan di BigQuery
Graph, GraphRAG yang menggabungkan traversal graph dengan potongan dokumen sebagai
konteks, pencarian vektor memakai embedding dan `VECTOR_SEARCH` di BigQuery, agent
retrieval yang memutuskan apa yang perlu diambil dari sebuah pertanyaan, dan agent
tanya-jawab sebagai permukaan bagi reliability engineer.

## Konteks

Fitur 001 menghasilkan rantai otonom `Scout → Investigator → Reporter` di atas
PostgreSQL + Apache AGE. Rantai itu menjawab pertanyaan yang **ARKA ajukan sendiri**:
mana yang layak diselidiki, dan kenapa mesin ini gagal.

Fitur ini menjawab kelas pertanyaan yang berbeda: **pertanyaan yang diajukan manusia**,
dalam bahasa bebas, yang jawabannya tersebar di graph dan di dokumen sekaligus.

Keduanya berbagi fondasi yang sama dan tidak boleh saling menggantikan. Rantai otonom
tetap identitas ARKA; tanya-jawab adalah permukaan tambahan di atas pengetahuan yang
sama — bukan pengganti otonominya, dan bukan alasan menyebut ARKA chatbot.

## Catatan Status

| Komponen | Status | Keterangan |
|---|---|---|
| Property graph di BigQuery | **Terbukti sebagian** | `CREATE PROPERTY GRAPH` dan `GRAPH_EXPAND` jalan di on-demand; preseden lintas pabrik menghasilkan angka identik dengan jalur lokal. Rantai deteksi belum memakainya |
| GraphRAG | **Belum ada** | Traversal dan sitasi dokumen sudah ada, tetapi belum pernah digabungkan sebagai konteks generasi |
| Pencarian vektor | **Belum ada** | Belum ada embedding sama sekali; pgvector terpasang tetapi kosong |
| Agent retrieval | **Belum ada** | Investigator mengambil data lewat jalur tetap, bukan dari pertanyaan bebas |
| Agent tanya-jawab | **Belum ada** | — |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bertanya dengan bahasa sendiri (Priority: P1)

Seorang reliability engineer mengetik pertanyaan apa adanya — *"seal filler mana saja
yang pernah bermasalah karena batch material?"* — dan menerima jawaban yang menyebutkan
mesin, pabrik, dan tindakan yang dulu berhasil, dengan rujukan ke dokumen sumbernya.

**Why this priority**: Tanpa ini, pengetahuan yang sudah dikumpulkan ARKA hanya bisa
diakses lewat temuan yang ia angkat sendiri. Engineer yang punya pertanyaan spesifik
tidak punya pintu masuk, dan pengetahuan itu kembali terkubur — persis masalah yang
ARKA ada untuk menyelesaikannya.

**Independent Test**: Ajukan pertanyaan yang jawabannya diketahui ada di jalur emas,
lalu periksa bahwa jawabannya menyebut pabrik yang benar dan membawa sitasi yang benar.

**Acceptance Scenarios**:

1. **Given** pertanyaan yang jawabannya berada di dokumen inspeksi, **When** engineer
   bertanya, **Then** jawabannya mengutip dokumen itu beserta penunjuk bagiannya.
2. **Given** pertanyaan yang jawabannya menuntut menyeberang antar pabrik,
   **When** engineer bertanya, **Then** jawabannya menyebut pabrik lain beserta
   kasusnya, bukan hanya pabrik yang ditanyakan.
3. **Given** pertanyaan yang tidak ada jawabannya di pengetahuan yang dimiliki,
   **When** engineer bertanya, **Then** sistem menyatakan tidak menemukan dasar yang
   cukup — dan tidak mengarang jawaban yang terdengar meyakinkan.

### User Story 2 - Menemukan lewat makna, bukan kata (Priority: P1)

Engineer menuliskan gejala dengan kalimatnya sendiri — *"produk merembes waktu
pengisian"* — dan sistem menemukan kasus historis yang mencatatnya sebagai *"kebocoran
produk di kepala pengisi"*, walaupun tidak satu kata pun sama.

**Why this priority**: Catatan pemeliharaan ditulis puluhan orang selama bertahun-tahun
tanpa kosakata seragam. Pencocokan kata membuat sebagian besar pengetahuan tak
terjangkau, dan justru catatan lama yang paling berharga.

**Independent Test**: Ajukan gejala dengan kata-kata yang sama sekali berbeda dari yang
tercatat, lalu periksa bahwa kasus yang benar tetap ditemukan.

**Acceptance Scenarios**:

1. **Given** gejala yang diungkapkan dengan kata berbeda, **When** dicari, **Then**
   kasus historis yang relevan tetap muncul dalam peringkat teratas.
2. **Given** pertanyaan yang memuat istilah yang tidak ada di kosakata manapun,
   **When** dicari, **Then** sistem mengembalikan hasil kosong, bukan hasil acak yang
   kebetulan mirip.

### User Story 3 - Jawaban yang bersandar pada graph dan dokumen sekaligus (Priority: P2)

Pertanyaan yang jawabannya menuntut dua-duanya — struktur *dan* teks — dijawab dengan
menggabungkan keduanya: hubungan antar aset dari graph, penjelasan dan tindakan dari
potongan dokumen.

**Why this priority**: Inilah yang membedakan dari RAG biasa. Pencarian teks tahu apa
yang tertulis; graph tahu apa yang terhubung. Pertanyaan keandalan yang sungguhan
hampir selalu menuntut keduanya.

**Independent Test**: Ajukan pertanyaan yang tidak terjawab oleh pencarian teks saja
maupun traversal saja, lalu periksa bahwa jawabannya memuat unsur dari kedua sumber.

**Acceptance Scenarios**:

1. **Given** pertanyaan tentang dampak sebuah sparepart ke armada, **When** dijawab,
   **Then** jawabannya menyebut aset terkait dari graph **dan** kutipan dokumen yang
   mendukungnya.
2. **Given** konteks yang terkumpul melebihi batas yang wajar, **When** jawaban
   disusun, **Then** konteks dipangkas menurut relevansi, dan pemangkasan itu tidak
   pernah membuang sitasi yang dipakai jawabannya.

### User Story 4 - Pengetahuan yang sama di penyimpanan produksi (Priority: P2)

Organisasi yang datanya sudah tinggal di BigQuery menjalankan ARKA tanpa memindahkan
data ke database lain, dan mendapat jawaban yang sama.

**Why this priority**: Menentukan apakah ARKA dapat dipasang di lingkungan nyata tanpa
menuntut infrastruktur baru — dan menghapus keberatan pertama yang biasanya muncul.

**Independent Test**: Jalankan pertanyaan yang sama terhadap kedua penyimpanan, lalu
bandingkan hasilnya baris demi baris.

**Acceptance Scenarios**:

1. **Given** data yang sama di kedua penyimpanan, **When** pertanyaan yang sama
   diajukan, **Then** kandidat dan skornya identik.
2. **Given** penyimpanan yang tidak dapat dijangkau, **When** pertanyaan diajukan,
   **Then** sistem menyatakan kegagalan itu terang-terangan, bukan menjawab dari
   sebagian data.

### Edge Cases

- Pertanyaan yang menyeret terlalu banyak simpul — penelusuran harus berhenti pada
  batas yang ditetapkan dan mengatakan bahwa hasilnya dipotong.
- Dokumen yang belum punya embedding — harus terlihat sebagai celah cakupan, bukan
  hilang diam-diam dari hasil.
- Pertanyaan di luar domain keandalan — dijawab dengan menyatakan batas cakupan.
- Pertanyaan yang meminta ARKA memilih di antara dua penyebab yang berselisih tipis —
  jawabannya menyajikan keduanya, konsisten dengan Prinsip IV.

## Requirements *(mandatory)*

### Retrieval

- **FR-001**: Sistem MUST menemukan kasus dan dokumen yang relevan secara makna,
  bukan hanya kecocokan kata.
- **FR-002**: Sistem MUST menggabungkan hasil penelusuran hubungan antar entitas
  dengan potongan dokumen menjadi satu konteks jawaban.
- **FR-003**: Sistem MUST membatasi kedalaman dan luas penelusuran, dan MUST
  menyatakan ketika hasil dipotong oleh batas itu.
- **FR-004**: Sistem MUST memberi peringkat hasil secara deterministik dan dapat
  dijelaskan, tanpa model bahasa menentukan urutannya.
- **FR-005**: Sistem MUST mengembalikan hasil kosong ketika tidak ada dasar yang
  cukup, dan MUST TIDAK menurunkan ambang demi menghasilkan sesuatu.

### Tanya-jawab

- **FR-006**: Setiap jawaban MUST membawa rujukan ke dokumen atau entitas yang
  menjadi dasarnya.
- **FR-007**: Sistem MUST menyatakan ketidaktahuan ketika pengetahuan yang dimiliki
  tidak menjawab pertanyaan.
- **FR-008**: Sistem MUST menolak menyimpulkan penyebab tunggal ketika bukti
  menunjukkan dua kemungkinan yang berselisih tipis, dan MUST menyajikan keduanya.
- **FR-009**: Nilai numerik dalam jawaban MUST berasal dari data, tidak dihitung
  ulang maupun ditulis ulang oleh model bahasa.
- **FR-010**: Sistem MUST menjaga jejak: pertanyaan, apa yang diambil, dan dari mana
  jawabannya bersumber.

### Portabilitas penyimpanan

- **FR-011**: Pengetahuan MUST dapat ditelusuri pada penyimpanan produksi tanpa
  mengubah lapisan penalaran maupun kontrak keluaran.
- **FR-012**: Pertanyaan yang sama pada data yang sama MUST menghasilkan kandidat
  dan skor yang identik di kedua penyimpanan.
- **FR-013**: Kegagalan penyimpanan MUST dilaporkan terang-terangan, bukan
  menghasilkan jawaban dari sebagian data.

### Batas

- **FR-014**: Permukaan tanya-jawab MUST TIDAK menggantikan rantai otonom; keduanya
  berbagi pengetahuan yang sama dan berjalan berdampingan.
- **FR-015**: Sistem MUST TIDAK menulis fakta baru ke pengetahuan sebagai akibat
  sebuah pertanyaan.

## Success Criteria *(mandatory)*

- **SC-001**: Untuk pertanyaan yang jawabannya diketahui ada, sistem mengembalikan
  jawaban yang benar beserta sitasi yang benar pada percobaan pertama.
- **SC-002**: Gejala yang diungkapkan dengan kata-kata berbeda dari catatan tetap
  menemukan kasus yang benar di peringkat lima teratas.
- **SC-003**: Pertanyaan yang tidak ada dasarnya dijawab dengan pernyataan tidak
  menemukan — nol jawaban karangan pada rangkaian uji.
- **SC-004**: Setiap jawaban yang memuat klaim substantif membawa sekurangnya satu
  rujukan yang dapat dibuka.
- **SC-005**: Pertanyaan yang sama pada kedua penyimpanan menghasilkan kandidat dan
  skor yang identik.
- **SC-006**: Seorang engineer memperoleh jawaban yang dapat ditindaklanjuti tanpa
  perlu tahu struktur data maupun bahasa kueri apa pun.

## Assumptions

- Domain tetap manufaktur FMCG multi-pabrik fiktif; tidak ada data klien.
- Pengetahuan yang dapat ditanyakan terbatas pada yang sudah ada di tabel kanonik dan
  dokumen — fitur ini tidak menambah sumber baru.
- Rantai `Scout → Investigator → Reporter` tetap berjalan dan tidak diubah oleh fitur
  ini; kontrak `Finding` tetap berlaku.
- Prinsip yang berlaku pada dokumen bukti berlaku pula pada jawaban: angka tidak
  melewati model, ketidakpastian dieskalasi, klaim membawa sitasi.
- Embedding dihasilkan sekali dari isi dokumen dan diperbarui ketika dokumennya
  berubah; pembaruan berkala berada di luar cakupan fitur ini.

## Key Entities

- **Pertanyaan**: Masukan bahasa bebas dari pengguna, beserta jejak apa yang diambil
  untuk menjawabnya.
- **Potongan dokumen**: Bagian dokumen yang dapat dikutip, beserta representasi
  maknanya untuk pencarian.
- **Konteks jawaban**: Gabungan entitas hasil penelusuran dan potongan dokumen yang
  menjadi dasar sebuah jawaban.
- **Jawaban**: Pernyataan beserta rujukannya, dan penanda ketika dasarnya tidak cukup.

## Ketergantungan

- Fitur 001 — lapisan deteksi deterministik dan kontrak `Finding`.
- Pengetahuan yang sudah terisi: tabel kanonik dan dokumen yang dapat dikutip.
