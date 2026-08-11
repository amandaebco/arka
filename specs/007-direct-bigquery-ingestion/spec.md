# Feature Specification: Direct BigQuery Ingestion Connector

**Feature Branch**: `007-direct-bigquery-ingestion`

**Created**: 2026-08-11

**Status**: Draft

**Input**: Konektor *direct ingestion* untuk menyerap data operasional (work order, failure event, aktivitas) langsung ke BigQuery tanpa melalui PostgreSQL perantara, serta mendukung alur kerja sinkronisasi otomatis.

## Konteks

Saat ini pembangkit data sintetis (`app/synthetic/generator.py`) menulis data ke PostgreSQL lokal, lalu disalin ke BigQuery via `scripts/migrasi_bigquery.py`.

Dalam lingkungan produksi nyata di GCP, data operasional masuk langsung ke BigQuery. Adanya perantara PostgreSQL lokal pada alur *ingestion* menjadi batasan operasional (`docs/submission.md#batasan-yang-diketahui` poin 1).

Fitur ini menghadirkan:
1. Modul konektor `app/bigquery/ingestion.py` yang dapat memasukkan atau memperbarui *canonical records* langsung ke tabel BigQuery (`insert_rows_json` / batch load).
2. Dukungan opsi `--bigquery` pada `app/synthetic/generator.py` untuk menulis data sintetis langsung ke BigQuery.
3. Otomatisasi pembentukan *property graph* (`graph_nodes` & `graph_edges`) langsung di BigQuery.

## User Scenarios & Testing

### User Story 1 - Direct Ingestion ke BigQuery (Priority: P1)

Seorang administrator data menjalankan penyerapan atau pembangkitan data dengan flag `--bigquery`. Data langsung ditulis ke tabel kanonik BigQuery dan node/edge list graph langsung diperbarui.

**Why this priority**: Menghilangkan ketergantungan pada PostgreSQL lokal untuk skenario produksi GCP murni.

**Independent Test**: Jalankan penyerapan data langsung ke BigQuery dataset uji, lalu pastikan jumlah baris di BigQuery cocok dan node/edge list graph berhasil terbangun.

**Acceptance Scenarios**:
1. **Given** koneksi BigQuery aktif, **When** konektor ingestion dipanggil dengan data tabel kanonik, **Then** data berhasil ditulis ke BigQuery tanpa error.
2. **Given** data berhasil ditulis ke BigQuery, **When** pembentukan graph dijalankan, **Then** `graph_nodes` dan `graph_edges` otomatis ter-update.

## Requirements

### Ingestion Connector

- **FR-001**: Modul `app/bigquery/ingestion.py` MUST menyediakan fungsi untuk melakukan batch load atau streaming insert ke tabel kanonik BigQuery.
- **FR-002**: Generator data `app/synthetic/generator.py` MUST mendukung argumen `--bigquery` untuk menulis data langsung ke BigQuery.
- **FR-003**: Setelah data ditulis ke BigQuery, sistem MUST otomatis memicu pembentukan `graph_nodes` dan `graph_edges`.

## Success Criteria

- **SC-001**: Data kanonik berhasil ditulis langsung ke BigQuery tanpa memerlukan database PostgreSQL perantara.
- **SC-002**: Seluruh unit test dan suite pengujian lulus 100%.
