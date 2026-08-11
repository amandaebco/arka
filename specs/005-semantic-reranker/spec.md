# Feature Specification: Lapisan Reranking untuk Pencarian Semantik GraphRAG

**Feature Branch**: `005-semantic-reranker`

**Created**: 2026-08-11

**Status**: Draft

**Input**: Lapisan reranker dan scoring fleksibel pada pencarian semantik dokumen GraphRAG untuk menggantikan ambang batas statis (cosine similarity floor 0.60) dengan evaluasi skor komposit (vektor + kata kunci domain + margin relatif).

## Konteks

Pencarian semantik pada `app/retrieval/vector_store.py` menggunakan `VECTOR_SEARCH` BigQuery dengan ambang batas Cosine Similarity statis `MIN_SIMILARITY = 0.60`.

Pengukuran pada korpus 54 dokumen / 104 potongan menunjukkan bahwa rentang skor pertanyaan *in-domain* (0.5889–0.7703) dan *out-of-domain* (0.4834–0.5896) saling bersinggungan di batas 0.5889 vs 0.5896. Ambang statis 0.60 berisiko membuang pertanyaan *in-domain* yang relevan atau meloloskan dokumen *out-of-domain* yang secara kebetulan memiliki nilai kemiripan mirip.

Fitur ini menghadirkan **Lapisan Reranker Komposit**:
1. Menarik kandidat pencarian vektor dengan ambang relaksasi awal (`MIN_SIMILARITY_CANDIDATE = 0.50`).
2. Menghitung skor overlap kata kunci domain (*equipment tags*, istilah komponen seperti `seal`, `torsi`, `katup`, `vibrasi`).
3. Mengombinasikan Cosine Similarity dan Keyword Score menjadi *Composite Rerank Score* (`0.65 * cosine + 0.35 * keyword`).
4. Menerapkan uji margin relatif terhadap kandidat teratas (*relative margin threshold*) untuk mempertahankan kandidat sekunder yang kuat dan membuang *outlier noise*.

## User Scenarios & Testing

### User Story 1 - Presisi & Recall Tinggi untuk Pertanyaan In-Domain (Priority: P1)

Seorang reliability engineer mengajukan pertanyaan dalam bahasa bebas yang memuat istilah domain (misal *"kenapa seal bocor di mesin filler PLT-U/FIL-207?"*). Sistem mengambil potongan dokumen yang relevan meskipun nilai Cosine Similarity mentahnya sedikit di bawah 0.60, karena skor kompositnya tinggi akibat kecocokan istilah domain.

**Why this priority**: Menghindari fenomena "jawaban kosong" (*false negative*) pada pertanyaan teknis yang valid akibat ambang batas statis yang terlalu kaku.

**Independent Test**: Jalankan pencarian dokumen dengan pertanyaan *in-domain* yang nilai Cosine Similarity mentahnya 0.58 tetapi memuat tag aset dan kata kunci komponen, lalu pastikan dokumen tersebut lolos dan berada di peringkat teratas.

**Acceptance Scenarios**:
1. **Given** pertanyaan *in-domain* dengan Cosine Similarity 0.58 dan keyword match domain, **When** `search()` dipanggil, **Then** dokumen tersebut dikembalikan oleh reranker.
2. **Given** pertanyaan *out-of-domain* (misal *"resep rendang padang"* atau *"harga saham"*), **When** `search()` dipanggil, **Then** hasil dikembalikan kosong karena skor komposit di bawah batas minimum 0.55.

### User Story 2 - Penyaringan Noise dengan Margin Relatif (Priority: P1)

Saat pencarian mengembalikan kandidat teratas yang sangat kuat (misal skor komposit 0.85) dan kandidat lain yang jauh lebih rendah (misal skor 0.51), reranker membuang kandidat yang nilai relatifnya di bawah 70% dari kandidat teratas.

**Why this priority**: Mencegah dokumen yang kurang relevan ikut menempel dalam konteks jawaban saat sudah ada dokumen utama yang sangat jelas dan kuat.

**Independent Test**: Berikan daftar kandidat dengan satu *hit* sangat dominan dan satu *hit* marginal, lalu pastikan *hit* marginal tereliminasi oleh filter margin relatif.

**Acceptance Scenarios**:
1. **Given** kandidat teratas dengan skor 0.85 dan kandidat sekunder dengan skor 0.51 (margin < 0.70), **When** `rerank_hits()` berjalan, **Then** hanya kandidat teratas yang diloloskan.

## Requirements

### Reranking Logic

- **FR-001**: Sistem MUST menarik kandidat awal dengan ambang relaksasi `MIN_SIMILARITY_CANDIDATE = 0.50`.
- **FR-002**: Sistem MUST menghitung skor overlap kata kunci domain (*equipment tags*, *component types*, *failure terms*).
- **FR-003**: Sistem MUST menghitung skor komposit dengan bobot `0.65` Cosine Similarity dan `0.35` Keyword Overlap Score.
- **FR-004**: Sistem MUST menyaring kandidat berdasarkan batas skor komposit minimum (`0.55`) dan margin relatif terhadap skor teratas (`>= 0.70`).
- **FR-005**: Lapisan reranker MUST bersifat opsional (`apply_rerank=True` secara default) agar kompatibel dengan pemanggilan pencarian mentah bila diperlukan.

## Success Criteria

- **SC-001**: Pertanyaan *in-domain* dengan skor kemiripan mentah 0.58-0.59 yang memuat istilah domain tetap berhasil ditemukan.
- **SC-002**: Pertanyaan *out-of-domain* mengembalikan hasil kosong (0 false positive).
- **SC-003**: Reranker berjalan cepat secara deterministik tanpa menambah latensi panggilan model eksternal.
