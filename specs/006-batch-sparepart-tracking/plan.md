# Implementation Plan: Automated Batch-Level Sparepart Tracking

**Feature**: `006-batch-sparepart-tracking`

**Created**: 2026-08-11

## Overview

Menambahkan kolom `batch_number` pada `ActivitySparePart` (`activity_spare_parts`), mendukung generasi data sintetis berkode batch, serta fungsi query `find_batch_installations` untuk melacak lokasi pemasangan lot material bermasalah lintas pabrik.

## Proposed Changes

### `app/models/maintenance.py`
- Tambahkan `batch_number = Column(String(50), nullable=True)` pada kelas `ActivitySparePart`.

### `app/detection/repository.py` & `app/detection/bigquery_repository.py`
- Tambahkan dataclass `BatchInstallation` dan fungsi `find_batch_installations(session, batch_number)`.

### `app/synthetic/generator.py` / `aktivitas.py`
- Sertakan `batch_number` pada pembentukan data aktivitas pemakaian sparepart.

### `tests/test_batch_tracking.py`
- Unit test untuk menguji skema `ActivitySparePart` dan fungsi `find_batch_installations`.

## Verification Plan

### Automated Tests
- Run `uv run pytest tests/test_batch_tracking.py`
- Run `uv run pytest` (seluruh suite test)
- Run `uv run ruff check .`
