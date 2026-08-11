# Feature Specification: Automated Batch-Level Sparepart Tracking

**Feature Branch**: `006-batch-sparepart-tracking`

**Created**: 2026-08-11

**Status**: Draft

**Input**: Menambahkan entitas dan atribut `batch_number` pada pencatatan aktivitas pemakaian sparepart (`activity_spare_parts`) untuk memungkinkan pelacakan kegagalan material hingga ke tingkat nomor lot/batch produksi lintas pabrik.

## Konteks

Saat ini pencatatan pemakaian sparepart pada aktivitas perawatan (`activity_spare_parts`) mencatat hubungan pekerjaan pemeliharaan dengan `spare_part_id`, `quantity`, dan `used_at`. Hal ini memungkinkan ARKA menjawab *"apa lagi yang memakai jenis part ini"*.

Namun di dunia industri nyata, kegagalan material sering kali terisolasi pada **lot/batch produksi tertentu** dari vendor. Tanpa atribut `batch_number`, pelacakan kegagalan material berhenti di tingkat jenis sparepart dan tidak dapat membedakan mana unit yang menggunakan batch bermasalah dari batch yang aman.

Fitur ini menghadirkan:
1. Atribut `batch_number` pada skema `activity_spare_parts`.
2. Kemampuan query pelacakan batch untuk mengetahui unit/pabrik mana lagi yang telah memasang sparepart dari lot/batch produksi yang sama.

## User Scenarios & Testing

### User Story 1 - Melacak Pemakaian Batch Material Lintas Pabrik (Priority: P1)

Saat sebuah komponen mengalami kegagalan akibat cacat lot material vendor, seorang reliability engineer dapat melacak nomor batch sparepart tersebut (misal `LOT-202602-B8801`) untuk mengetahui unit dan pabrik mana saja yang sudah atau akan memasang material dari batch yang sama.

**Why this priority**: Menghindari kegagalan berulang akibat lot material cacat vendor yang terlanjur terpasang di pabrik lain sebelum mesinnya rusak.

**Independent Test**: Buat data pemakaian sparepart dengan `batch_number`, lalu jalankan query pelacakan batch untuk memastikan seluruh equipment dan pabrik yang menggunakan batch tersebut teridentifikasi secara tepat.

**Acceptance Scenarios**:
1. **Given** sparepart yang terpasang dengan `batch_number = 'LOT-202602-B8801'`, **When** query pelacakan batch dijalankan, **Then** sistem mengembalikan daftar equipment, work order, dan pabrik yang menggunakan batch tersebut.
2. **Given** sparepart tanpa `batch_number` (kasus legacy), **When** query dijalankan, **Then** sistem memperlakukan `batch_number` sebagai `None` tanpa menyebabkan error.

## Requirements

### Data Model & Schema

- **FR-001**: Skema `activity_spare_parts` MUST memiliki kolom `batch_number` (string opsional).
- **FR-002**: Generator sintetis (`app/synthetic/`) MUST dapat membangkitkan `batch_number` untuk pemakaian sparepart jalur emas.

### Query & Tracking

- **FR-003**: Sistem MUST menyediakan fungsi query `find_batch_installations(batch_number)` yang mengembalikan lokasi terpasang (equipment tag, pabrik, tanggal pemasangan, work order ID).

## Success Criteria

- **SC-001**: Pelacakan batch mengembalikan lokasi equipment dan pabrik yang tepat untuk nomor lot material tertentu.
- **SC-002**: Seluruh unit test dan suite pengujian lulus 100%.
