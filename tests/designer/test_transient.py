"""Tests for transient-failure retries.

The risk being guarded here is not that a retry fails to happen. It is that a
retry quietly turns a failure into a success, or that a permanent failure gets
retried three times at full cost. Both are tested below.
"""

from __future__ import annotations

import pytest

from app.designer.transient import is_transient, with_retry


class GalatSementara(Exception):
    """Stands in for a provider 5xx; recognised by its status code."""

    status_code = 520


class GalatTetap(Exception):
    """A request that is wrong will be just as wrong on the next attempt."""


def diam(_pause: float) -> None:
    """Swallow the backoff so tests do not pay for it in wall-clock time."""


def test_galat_transport_dikenali():
    assert is_transient(GalatSementara())
    assert is_transient(type("RemoteProtocolError", (Exception,), {})())


def test_galat_permintaan_bukan_transien():
    assert not is_transient(GalatTetap())
    assert not is_transient(type("BadRequestError", (Exception,), {"status_code": 400})())


def test_gagal_sementara_lalu_berhasil():
    percobaan = {"n": 0}

    def call():
        percobaan["n"] += 1
        if percobaan["n"] < 3:
            raise GalatSementara("server sedang tidak sehat")
        return "halaman"

    assert with_retry(call, what="uji", sleep=diam) == "halaman"
    assert percobaan["n"] == 3


def test_galat_tetap_tidak_diulang():
    """Retrying a permanent failure spends money to reach the same answer."""
    percobaan = {"n": 0}

    def call():
        percobaan["n"] += 1
        raise GalatTetap("prompt ditolak")

    with pytest.raises(GalatTetap):
        with_retry(call, what="uji", sleep=diam)
    assert percobaan["n"] == 1


def test_habis_percobaan_tetap_gagal():
    """Retrying widens the window to succeed; it never lowers the bar for one."""
    percobaan = {"n": 0}

    def call():
        percobaan["n"] += 1
        raise GalatSementara("tetap tidak sehat")

    with pytest.raises(GalatSementara):
        with_retry(call, what="uji", attempts=3, sleep=diam)
    assert percobaan["n"] == 3
