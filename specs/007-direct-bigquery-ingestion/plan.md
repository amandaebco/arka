# Implementation Plan: Direct BigQuery Ingestion Connector

**Feature**: `007-direct-bigquery-ingestion`

**Created**: 2026-08-11

## Overview

Menyediakan modul konektor `app/bigquery/ingestion.py` untuk batch load data kanonik langsung ke BigQuery, menambahkan dukungan argumen `--bigquery` pada generator sintetis, serta unit test terisolasi.

## Proposed Changes

### `app/bigquery/ingestion.py`
- Menyediakan fungsi:
  - `load_table_records(table_name, records) -> int`: Melakukan JSON batch load ke tabel BigQuery target.
  - `ingest_canonical_dataset(dataset_dict) -> dict[str, int]`: Memuat seluruh kamus record kanonik dan memicu pembentukan graph list.

### `app/synthetic/generator.py`
- Tambahkan dukungan argumen `--bigquery` pada `main()` dan `bangun()` untuk menulis data langsung ke BigQuery.

### `tests/test_bigquery_ingestion.py`
- Unit test untuk menguji fungsi `ingestion.py`.

## Verification Plan

### Automated Tests
- Run `uv run pytest tests/test_bigquery_ingestion.py`
- Run `uv run pytest` (seluruh suite test)
- Run `uv run ruff check .`
