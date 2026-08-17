"""Tes selalu membaca PostgreSQL, apa pun sumber bawaan produksi.

`ARKA_STORE` bawaannya `postgres` sejak 17 Agustus. Tanpa berkas
ini, tes agent ikut terbawa ke sana — terukur: `test_scout_agent.py` melonjak
dari sepersekian detik menjadi 47 detik per setup, dan suite penuh dari 12 detik
menjadi 261.

Kecepatan bukan alasan utamanya. PostgreSQL adalah tempat generator sintetis
menulis, jadi ia satu-satunya penyimpanan yang isinya dijamin sesuai kode yang
sedang diuji. Menguji terhadap BigQuery berarti menguji terhadap **salinan
terakhir yang disinkronkan** — dan tes yang merah karena sinkronisasi belum
dijalankan mengajari orang untuk mengabaikan tes merah.

Konsekuensinya jujur: jalur BigQuery **tidak** ditutup suite ini. Yang
menjaganya adalah pengujian paritas yang dijalankan tangan setelah migrasi.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def pakai_postgres(monkeypatch):
    """Kunci seluruh tes ke PostgreSQL.

    `tests/test_store_dispatch.py` menghapus variabel ini lagi di fixture-nya
    sendiri, karena yang diujinya justru perilaku bawaan.
    """
    monkeypatch.setenv("ARKA_STORE", "postgres")
