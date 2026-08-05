-- Extension yang dibutuhkan ARKA.
-- Dijalankan otomatis oleh entrypoint container saat volume masih kosong.

CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Graph dibuat oleh app/graph/project.py, bukan di sini,
-- supaya proyeksi bisa membangun ulang dari nol kapan pun.
