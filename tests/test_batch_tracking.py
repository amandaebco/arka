"""Unit tests for batch-level sparepart tracking (Feature 006)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.retrieval.batch_tracking import BatchInstallation, find_batch_installations


@pytest.fixture
async def database():
    from app.db.session import session_factory

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unavailable: {type(exc).__name__}")
    return True


class TestBatchTrackingDataclass:
    def test_batch_installation_fields(self):
        install = BatchInstallation(
            batch_number="LOT-202602-B8801",
            part_number="SP-SEAL-8801",
            part_name="Seal Kepala Pengisi",
            equipment_tag="PLT-U/FIL-207",
            plant="Pabrik Utara",
            work_order_number="WO-2026-001",
            installed_on=None,
        )
        assert install.batch_number == "LOT-202602-B8801"
        assert install.equipment_tag == "PLT-U/FIL-207"


class TestFindBatchInstallations:
    async def test_find_batch_installations_empty_returns_list(self, database):
        from app.db.session import session_factory

        async with session_factory() as session:
            results = await find_batch_installations(session, "LOT-NON-EXISTENT")
            assert results == []
