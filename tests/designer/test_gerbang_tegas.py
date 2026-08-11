"""Tests that the page gate cannot be talked past.

On a live run the reviewer called `selesai` and declared the page fit to send
while its own check had just reported unauthorised text and a card that was
never drawn. A compensating control that a model can decide to ignore is not a
control, so the refusal lives in code.
"""

from __future__ import annotations

from app.agents.qa import KUNCI_HALAMAN_LULUS, selesai


class KonteksPalsu:
    def __init__(self, state: dict):
        self.state = state
        self.actions = type("Aksi", (), {"escalate": False})()


def test_halaman_gagal_tidak_boleh_dinyatakan_layak():
    ctx = KonteksPalsu({KUNCI_HALAMAN_LULUS: False})
    hasil = selesai("terlihat baik menurut saya", ctx)
    assert hasil.startswith("DITOLAK")
    assert ctx.actions.escalate is False, "putaran perbaikan tidak boleh berhenti"


def test_halaman_lulus_boleh_ditutup():
    ctx = KonteksPalsu({KUNCI_HALAMAN_LULUS: True})
    hasil = selesai("seluruh pemeriksaan lulus", ctx)
    assert hasil.startswith("Dokumen dinyatakan layak kirim")
    assert ctx.actions.escalate is True


def test_jalur_dokumen_tidak_ikut_terhalang():
    """The document reviewer never reads a page, so it must not be blocked by a
    verdict that was never recorded."""
    ctx = KonteksPalsu({})
    assert selesai("memo lengkap", ctx).startswith("Dokumen dinyatakan layak kirim")
    assert ctx.actions.escalate is True
