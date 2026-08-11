# Tasks: Automated Batch-Level Sparepart Tracking

**Feature**: `006-batch-sparepart-tracking`

## Tasks

- [x] **Task 1**: Buat spesifikasi Spec Kit (`specs/006-batch-sparepart-tracking/spec.md`, `plan.md`, `tasks.md`)
- [x] **Task 2**: Update model `ActivitySparePart` di `app/models/maintenance.py` dengan kolom `batch_number`
- [x] **Task 3**: Update `app/detection/repository.py` dan `app/detection/bigquery_repository.py` dengan `BatchInstallation` & `find_batch_installations`
- [x] **Task 4**: Update generator data sintetis `app/synthetic/` untuk membangkitkan `batch_number`
- [x] **Task 5**: Buat unit test `tests/test_batch_tracking.py` dan pastikan seluruh test suite `pytest` lulus 100%
