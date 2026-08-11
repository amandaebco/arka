# Implementation Plan: Lapisan Reranking untuk Pencarian Semantik GraphRAG

**Feature**: `005-semantic-reranker`

**Created**: 2026-08-11

## Overview

Mengimplementasikan lapisan reranker untuk pencarian semantik dokumen GraphRAG yang menggabungkan Cosine Similarity dari `VECTOR_SEARCH` BigQuery, Lexical Keyword Overlap, dan Relative Margin Filter.

## Proposed Changes

### `app/retrieval/reranker.py`
- Modul baru yang menyediakan:
  - `calculate_keyword_overlap(question, content, title) -> float`
  - `rerank_hits(question, hits, min_composite=0.55, min_relative_margin=0.70) -> list[SemanticHit]`

### `app/retrieval/vector_store.py`
- Menyiapkan `MIN_SIMILARITY_CANDIDATE = 0.50` untuk penarikan candidate pool.
- Mengubah fungsi `search(question, limit=5, apply_rerank=True)` agar memanfaatkan `rerank_hits`.

### `tests/test_reranker.py`
- Unit test komprehensif untuk pengujian `calculate_keyword_overlap`, `rerank_hits`, penyaringan noise, dan filter margin relatif.

## Verification Plan

### Automated Tests
- Run `uv run pytest tests/test_reranker.py`
- Run `uv run pytest` (seluruh suite test)
- Run `uv run ruff check .`
