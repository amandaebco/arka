# Tasks: Lapisan Retrieval Produksi — Graph, Vektor, dan Tanya-Jawab

**Feature**: 003-bigquery-graphrag · **Plan**: [plan.md](./plan.md) · **Date**: 2026-08-11

⚠️ **Status penulisan.** Daftar ini disusun **setelah** implementasinya selesai,
sebagai pemetaan requirement → kode → tes. Tanda `[X]` di sini berarti "terbukti
ada dan teruji", bukan "dikerjakan mengikuti daftar ini". Alasannya di
[plan.md](./plan.md). Butir yang masih `[ ]` benar-benar belum dikerjakan.

**Language**: Kode, komentar, dan prompt dalam bahasa Inggris. String yang sampai ke
pengguna akhir tetap bahasa Indonesia.

---

## Phase 1 — Pengetahuan di penyimpanan produksi

- [X] T001 Petakan tabel kanonik ke skema BigQuery di `app/bigquery/schema.py` (FR-011)
- [X] T002 Salin isi PostgreSQL ke BigQuery di `app/bigquery/sync.py` (FR-011)
- [X] T003 Proyeksikan node dan edge dari tabel kanonik di `app/bigquery/edges.py` (FR-011)
- [X] T004 [P] Kunci bentuk skema terhadap regresi di `tests/test_bigquery_schema.py`

## Phase 2 — Traversal tanpa lisensi Enterprise

- [X] T005 Terapkan traversal recursive CTE dengan kedalaman sebagai parameter di
  `app/bigquery/traversal.py` (FR-002, FR-003)
- [X] T006 Batasi kedalaman dan luas agar penelusuran selalu berhenti (FR-003)
- [X] T007 Sediakan tool `telusuri_graph` bagi agent tanya-jawab (FR-002)
- [X] T008 [P] Buktikan jalur lengkap dikembalikan sebagai data di
  `tests/test_telusuri_graph.py`

## Phase 3 — Pencarian lewat makna

- [X] T009 Potong dokumen di batas paragraf dengan tumpang tindih di
  `app/retrieval/chunking.py` (FR-001)
- [X] T010 Hasilkan embedding 3072 dimensi di luar BigQuery di
  `app/retrieval/embedding.py` (FR-001)
- [X] T011 Cari dengan `VECTOR_SEARCH` di `app/retrieval/vector_store.py` (FR-001, FR-004)
- [X] T012 Kembalikan hasil kosong di bawah ambang, bukan hasil terbaik yang lemah (FR-005)
- [X] T013 [P] Ukur pengaruh pemotongan terhadap ambang di `tests/test_chunking.py`
- [X] T014 Indeks korpus lewat `scripts/migrasi_bigquery.py --index`

## Phase 4 — GraphRAG dan permukaan tanya-jawab

- [X] T015 Tarik traversal dan potongan dokumen sebagai satu konteks di
  `app/retrieval/graphrag.py` (FR-002)
- [X] T016 Pisahkan `retriever` dari `answerer` di `app/agents/tanya_jawab.py` (FR-006)
- [X] T017 Tolak klaim tanpa rujukan yang dapat dibuka (FR-006, SC-004)
- [X] T018 Nyatakan ketidaktahuan ketika dasarnya tidak cukup (FR-007, SC-003)
- [X] T019 Larang penyimpulan penyebab tunggal saat bukti bertentangan (FR-008)
- [X] T020 Sajikan sebagai agent terlayani di `adk_agents/tanya_jawab/`

## Phase 5 — Dua penyimpanan, satu lapisan penalaran

- [X] T021 Sediakan antarmuka yang sama atas BigQuery di
  `app/detection/bigquery_repository.py` (FR-011, FR-012)
- [X] T022 Pilih penyimpanan lewat `ARKA_STORE` di `app/detection/store.py`; nilai tak
  dikenal jatuh ke PostgreSQL, bukan ke cloud (FR-013)
- [X] T023 [P] Kunci perilaku bawaan yang aman di `tests/test_store_dispatch.py`
- [X] T024 Tolak menjawab dari salinan basi di `app/bigquery/kesegaran.py` (FR-013)
- [X] T025 [P] Buktikan penjaga kesegaran menghentikan jalan di `tests/test_kesegaran.py`
- [X] T026 Bandingkan kedua sisi lewat `scripts/migrasi_bigquery.py --verify` (SC-005)

## Phase 6 — Pengukuran dan sisa

- [X] T027 Ukur ambang kemiripan atas korpus nyata, bukan menebaknya — 0,60 (SC-002)
- [X] T028 Rangkaian pertanyaan uji di `scripts/uji_golden_prompts.py` (SC-001, SC-003)
- [ ] T029 Ukur ulang ambang 0,60 setelah korpus melewati ~500 dokumen — angka
  sekarang adalah properti korpus 54 dokumen, dan akan salah di produksi
- [ ] T030 Jadikan BigQuery sumber langsung sehingga langkah sinkronisasi hilang
  beserta mode gagal salinan basinya
- [ ] T031 Perbarui embedding secara berkala ketika dokumen sumbernya berubah
  (dinyatakan di luar cakupan pada [spec.md](./spec.md), dicatat di sini agar tidak hilang)

---

## Dependencies

```text
Phase 1 → Phase 2 → Phase 4
   ↓         ↓
Phase 5   Phase 3 → Phase 4 → Phase 6
```

- Phase 1 memblokir segalanya; tidak ada yang bisa ditelusuri sebelum pengetahuannya ada.
- Phase 3 tidak bergantung pada Phase 2 — makna dan struktur adalah dua jalur terpisah
  yang baru bertemu di Phase 4. Itu justru yang membuat GraphRAG bermakna di sini.
- Phase 5 dapat berjalan sejajar dengan Phase 3.

## Implementation strategy

**MVP adalah Phase 1 + 2 + 5.** Itu saja sudah memindahkan rantai otonom ke
penyimpanan produksi dengan angka yang terbukti identik — nilai yang paling sulit
dibantah. Phase 3 dan 4 menambahkan kelas pertanyaan baru di atasnya.

Kalau waktu habis, potong dengan urutan: T031, T030, T028. **Jangan potong T024** —
menjawab dari salinan basi adalah satu-satunya mode gagal di fitur ini yang diam.
