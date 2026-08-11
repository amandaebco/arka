# Implementation Plan: Lapisan Retrieval Produksi — Graph, Vektor, dan Tanya-Jawab

**Branch**: `feat/rantai-pelaporan` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-bigquery-graphrag/spec.md`

⚠️ **Catatan kejujuran urutan.** Rencana ini ditulis **setelah** implementasinya
berjalan, pada hari yang sama dengan spec-nya. Ia mencatat rancangan sebagaimana
dibangun, bukan rancangan yang memandu pembangunan. Spec 001 memandu implementasi
dari depan; fitur ini tidak. Perbedaan itu dituliskan di sini alih-alih disamarkan,
karena rencana yang tampak memandu padahal menyusul adalah kebohongan yang paling
mudah dibantah oleh `git log`.

## Summary

Fitur 001 menjawab pertanyaan yang ARKA ajukan sendiri. Fitur ini menjawab
pertanyaan yang diajukan manusia, dan menjalankan keduanya di atas penyimpanan
produksi yang sama.

Tiga hal digabungkan. Pertama, pengetahuan dipindahkan ke BigQuery sebagai daftar
node dan edge atas tabel kanonik, ditelusuri dengan recursive CTE — bukan dengan
sintaks GQL, yang menuntut lisensi Enterprise. Kedua, dokumen dipotong pada batas
paragraf, disematkan di luar BigQuery, dan dicari dengan `VECTOR_SEARCH`. Ketiga,
keduanya ditarik bersama sebagai satu konteks jawaban, lalu disajikan lewat agent
tanya-jawab yang memisahkan *apa yang diambil* dari *apa yang didukung bukti*.

Yang tidak berubah: `app/detection/` di atasnya bekerja pada dataclass, jadi
penggantian penyimpanan tidak menyentuh satu baris pun logika penilaian.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Google ADK 2.x · google-cloud-bigquery ·
google-genai (`gemini-embedding-2`, 3072 dimensi) · Pydantic 2

**Storage**: BigQuery sebagai sumber produksi (`graph_nodes` / `graph_edges` +
`VECTOR_SEARCH`); PostgreSQL 16 + Apache AGE tetap sumber kebenaran generator
sintetis dan tes. `ARKA_STORE` memilih di antaranya

**Testing**: pytest (asyncio auto). Traversal, chunking, dan dispatcher diuji tanpa
jaringan; paritas dua penyimpanan diuji sebagai perbandingan angka, bukan sebagai
klaim

**Target Platform**: Cloud Run, image yang sama dengan fitur 001

**Performance Goals**: Satu pertanyaan dijawab dalam satu giliran interaktif;
kedalaman traversal adalah parameter dengan batas, bukan rekursi terbuka

**Constraints**: Embedding dibuat **di luar** BigQuery. `ML.GENERATE_EMBEDDING`
menuntut koneksi remote model yang service account-nya perlu akses Vertex, dan akun
ini tidak boleh `setIamPolicy`. `VECTOR_SEARCH` sendiri tidak menuntut koneksi apa pun

**Scale/Scope**: 6.471 node · 10.094 edge · 13 label · 16 jenis relasi ·
104 potongan dari 54 dokumen

## Constitution Check

*GATE: diperiksa terhadap rancangan sebagaimana dibangun.*

| Prinsip | Bagaimana rancangan ini memenuhinya | Verdict |
|---|---|---|
| I. Angka deterministik | Peringkat, jarak vektor, dan kedalaman traversal dihitung kueri. Model menerima keduanya sebagai data dan tidak boleh menghitung ulang (FR-004, FR-009) | PASS |
| II. Klaim membawa sitasi | Setiap potongan membawa dokumen asalnya; `answerer` menolak klaim tanpa rujukan (FR-006) | PASS |
| III. Agent tidak menulis fakta | Seluruh lapisan ini **read-only**. Tidak ada jalur tulis ke pengetahuan (FR-015) | PASS |
| IV. Ketidakpastian dieskalasi | Di bawah ambang kemiripan, sistem menyatakan tidak menemukan alih-alih menjawab (FR-005, FR-007) | PASS |
| V. Otonomi tidak ditukar | Tanya-jawab adalah permukaan tambahan; rantai otonom tidak diubah (FR-014) | PASS |
| VI. Kegagalan terang-terangan | Salinan BigQuery yang basi menghentikan jalan, bukan menjawab diam-diam (FR-013) | PASS |

## Phase 0 — Yang perlu diputuskan lebih dulu

| Pertanyaan | Keputusan | Alasan |
|---|---|---|
| BigQuery Graph (`GRAPH … MATCH`) atau recursive CTE? | **Recursive CTE** | `CREATE PROPERTY GRAPH` dan `GRAPH_EXPAND` berjalan on-demand; sintaks GQL penuh menuntut Enterprise. Yang dibayar adalah sintaksnya, bukan kemampuan menelusuri |
| Embedding di dalam atau di luar BigQuery? | **Di luar** | `ML.GENERATE_EMBEDDING` menuntut koneksi remote model + IAM yang tidak tersedia |
| Ambang kemiripan | **0,60**, diukur | Pertanyaan berbeda kata mencapai 0,61–0,72; di luar domain masih 0,56. Properti korpus, bukan properti model — wajib diukur ulang saat korpus tumbuh |
| Satu penyimpanan atau dua? | **Dua, dengan dispatcher** | Generator sintetis dan tes butuh PostgreSQL; produksi butuh BigQuery. Nilai `ARKA_STORE` tak dikenal jatuh ke PostgreSQL, **bukan** ke cloud |

## Phase 1 — Rancangan

```
app/bigquery/schema.py      daftar tabel kanonik → skema BigQuery
app/bigquery/sync.py        salin dari PostgreSQL
app/bigquery/edges.py       proyeksi node dan edge dari tabel kanonik
app/bigquery/traversal.py   recursive CTE, kedalaman sebagai parameter
app/bigquery/kesegaran.py   penjaga: menolak menjawab dari salinan basi
app/detection/store.py      dispatcher ARKA_STORE, bawaan aman
app/detection/bigquery_repository.py   antarmuka sama, penyimpanan lain
app/retrieval/chunking.py   potong di batas paragraf, dengan tumpang tindih
app/retrieval/embedding.py  gemini-embedding-2, 3072 dimensi
app/retrieval/vector_store.py  VECTOR_SEARCH
app/retrieval/graphrag.py   traversal + potongan sebagai satu konteks
app/agents/tanya_jawab.py   retriever (apa yang diambil) + answerer (apa yang didukung)
```

Batas yang dijaga: `app/detection/repository.py` dan `bigquery_repository.py`
mengembalikan dataclass yang sama. Itulah satu-satunya alasan paritas bisa diukur
alih-alih diklaim.

## Risiko yang diterima

1. **Salinan BigQuery bisa basi.** Diisi dari PostgreSQL lewat
   `scripts/migrasi_bigquery.py`. Penjaga kesegaran menutup mode gagal diamnya,
   tetapi tidak menghilangkan langkahnya. Di produksi BigQuery menjadi sumber
   langsung dan langkah ini hilang.
2. **Ambang 0,60 diukur atas korpus kecil.** Berlaku untuk 54 dokumen; angka ini
   akan salah pada korpus produksi dan harus diukur ulang.
3. **Embedding di luar BigQuery** berarti pembaruan dokumen tidak otomatis
   memperbarui vektornya — di luar cakupan fitur ini, dan disebutkan di spec.
