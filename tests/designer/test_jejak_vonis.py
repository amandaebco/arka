"""Tests for verdicts reaching the audit trail.

The trail is the third compensating control behind the infographic exception.
A trail that records three pages without recording why two were rejected leaves
an auditor unable to check the very thing the exception rests on.
"""

from __future__ import annotations

import json

from app.designer.trail import RunTrail, record_verdict


def test_vonis_menyusul_setelah_jejak_ditutup(tmp_path):
    """The publication tool closes the trail before the reviewer ever runs, so
    the verdict has to be able to arrive late."""
    trail = RunTrail("ARKA-2026-0042", base=tmp_path)
    trail.finish("PUBLISHED")

    record_verdict(trail.dir, "teks_tergambar", "Teks tak berasal dari kanvas: “Kritikalitas”")
    record_verdict(trail.dir, "putusan", "Dokumen dinyatakan layak kirim.")

    log = json.loads((trail.dir / "run.json").read_text(encoding="utf-8"))
    assert [r["stage"] for r in log["reviews"]] == ["teks_tergambar", "putusan"]
    assert "Kritikalitas" in log["reviews"][0]["verdict"]
    assert log["outcome"] == "PUBLISHED"  # tahap sebelumnya tidak tertimpa


def test_jejak_yang_belum_ada_tidak_menjatuhkan_pemeriksa(tmp_path):
    """Losing the evidence must never take the run down with it."""
    record_verdict(tmp_path / "belum-ada", "putusan", "layak kirim")


def test_bucket_dibaca_dari_settings_bukan_lingkungan(monkeypatch, tmp_path):
    """`.env` is loaded by pydantic and never reaches os.environ, so reading the
    environment directly ignored a bucket that was configured — silently, with
    every local trail losing its permanent copy and nothing saying so.
    """
    import app.designer.trail as jejak
    from app.core.config import get_settings

    monkeypatch.delenv("ARTIFACT_GCS_BUCKET", raising=False)
    get_settings.cache_clear()
    monkeypatch.setenv("ARTIFACT_GCS_BUCKET", "")

    dipakai: list[str] = []
    monkeypatch.setattr(
        jejak, "_mirror",
        lambda prefix, name, payload, ct: dipakai.append(prefix),
    )

    trail = jejak.RunTrail("ARKA-2026-0042", base=tmp_path)
    trail.finish("PUBLISHED")
    assert dipakai, "penyalinan tidak pernah dipanggil"

    get_settings.cache_clear()
    assert "artifact_gcs_bucket" in type(get_settings()).model_fields
