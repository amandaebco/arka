"""Chromium benar-benar menghasilkan PDF — satu tes, dan ia tahu diri.

`tests/test_reporter_agent.py` mengganti perendernya dengan yang mengembalikan
bita, karena yang diuji di sana kontrak tool. Tetapi klaim "reporter menerbitkan
PDF" tetap perlu satu tes yang memanggil peramban sungguhan, kalau tidak tidak
ada yang menjaga jalur itu sama sekali.

Tes ini **melewati dirinya sendiri** ketika Chromium tidak terpasang. Suite ARKA
berjalan tanpa jaringan, tanpa database, dan tanpa model; peramban adalah
ketergantungan sejenis, dan CI tidak memilikinya. Melewati dengan alasan yang
tertulis lebih jujur daripada merah yang menuduh kode padahal yang kurang
lingkungannya — dan lebih jujur pula daripada menghapus tesnya.
"""

import pytest

from app.reporting.dokumen import JENIS
from app.reporting.memo import render_dokumen_pdf
from app.synthetic.finding_contoh import finding_contoh

# Penanda yang dipakai Playwright ketika binari peramban belum diunduh. Dicocokkan
# pada pesan, bukan pada tipe: kegagalan sungguhan harus tetap merah, dan hanya
# "peramban tidak ada" yang boleh berubah jadi lewat.
TANDA_TIDAK_TERPASANG = ("executable doesn't exist", "playwright install", "browsertype.launch")


async def test_pdf_terbentuk_dari_finding():
    try:
        isi = await render_dokumen_pdf(finding_contoh(), JENIS["memo"], [], {}, None)
    except Exception as exc:  # noqa: BLE001 — dipilah di bawah, bukan ditelan
        pesan = str(exc).lower()
        if any(tanda in pesan for tanda in TANDA_TIDAK_TERPASANG):
            pytest.skip(f"Chromium tidak terpasang di lingkungan ini: {type(exc).__name__}")
        raise

    # Header berkas, bukan sekadar "ada isinya": HTML yang gagal dicetak juga
    # mengembalikan bita, dan bita yang bukan PDF adalah kegagalan yang lolos.
    assert isi.startswith(b"%PDF-"), "keluaran bukan berkas PDF"
    assert len(isi) > 10_000, "PDF terlalu kecil untuk memuat satu halaman memo"
