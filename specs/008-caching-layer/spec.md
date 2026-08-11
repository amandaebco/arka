# Feature Specification: Multi-Tier Caching Layer & Performance Optimization

**Feature Branch**: `008-caching-layer`

**Created**: 2026-08-11

**Status**: In Progress

**Input**: Modul caching in-memory terpusat (TTL-based) untuk mengoptimalkan performa eksekusi query GraphRAG, pencarian vector retrieval, dan penggunaan token LLM pada agent ARKA.

## Konteks

Saat ini setiap investigasi agent melakukan eksekusi ulang query GraphRAG (BigQuery & Apache AGE) serta operasi retrieval vektor. Untuk query yang berulang atau memiliki struktur data yang sama, eksekusi ulang tanpa cache dapat menambah latensi dan konsumsi kuota/biaya API.

Fitur ini menghadirkan:
1. Modul terpusat `app/core/cache.py` yang menyediakan struktur data `TTLCache` (thread-safe, eviction policy, TTL, serta pengumpulan statistik hits/misses).
2. Decorator `@cached` yang mendukung fungsi sinkron maupun asinkron.
3. Integrasi cache pada query GraphRAG (`app/graph/neighborhood.py`), pencarian vektor (`app/retrieval/vector_store.py`), serta pengaturan *thinking budget* per agent untuk meminimalkan *latency overhead*.

## User Scenarios & Testing

### User Story 1 - In-Memory Cache untuk Query GraphRAG & Retrieval (Priority: P1)

Pengguna/Agent melakukan investigasi pada tag peralatan yang sama. Sistem mengambil data dari cache lokal jika belum kadaluarsa (TTL), sehingga pemanggilan database/API berulang dihindari.

**Why this priority**: Mengurangi latensi eksekusi dari hitungan detik ke milidetik dan menghemat biaya API.

**Acceptance Scenarios**:
1. **Given** query graph untuk tag peralatan tertentu dipanggil pertama kali, **When** fungsi dieksekusi, **Then** hasil query disimpan di cache dan dihitung sebagai cache miss.
2. **Given** query yang sama dipanggil kedua kali dalam durasi TTL, **When** fungsi dieksekusi, **Then** hasil diambil dari cache tanpa memanggil database dan dihitung sebagai cache hit.

## Requirements

### Caching Module
- **FR-001**: Modul `app/core/cache.py` MUST menyediakan kelas `TTLCache` dengan dukungan `get`, `set`, `clear`, `stats` (hits, misses, hit_ratio), dan otomatis pembersihan item yang kadaluarsa.
- **FR-002**: Modul MUST menyediakan decorator `@cached(cache_instance, ttl, prefix)` yang bekerja transparan untuk fungsi sync dan async.
- **FR-003**: Sistem MUST menyediakan unit test komprehensif di `tests/test_cache.py` dengan passing rate 100%.

## Success Criteria

- **SC-001**: Seluruh fungsi cache teruji lulus 100% pada pengujian otomatis.
- **SC-002**: Latensi pemanggilan ulang query yang ter-cache berkurang >90%.
