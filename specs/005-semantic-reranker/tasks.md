# Tasks: Lapisan Reranking untuk Pencarian Semantik GraphRAG

**Feature**: `005-semantic-reranker`

## Tasks

- [x] **Task 1**: Buat spesifikasi Spec Kit (`specs/005-semantic-reranker/spec.md`, `plan.md`, `tasks.md`)
- [x] **Task 2**: Implementasikan modul reranker `app/retrieval/reranker.py` dengan kalkulasi keyword overlap dan relative margin filtering
- [x] **Task 3**: Integrasikan `rerank_hits` ke dalam `search()` di `app/retrieval/vector_store.py`
- [x] **Task 4**: Buat unit test `tests/test_reranker.py` untuk menguji fungsionalitas reranker
- [x] **Task 5**: Jalankan linting `ruff check` dan pastikan seluruh test suite `pytest` lulus 100%
