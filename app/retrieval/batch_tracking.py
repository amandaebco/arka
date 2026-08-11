"""Batch-level sparepart tracking for material failure investigations.

Traces installed sparepart batches (`batch_number`) across equipment, work orders,
and plants. This lives in the retrieval layer rather than in `app/detection/`
to keep the core detection arithmetic immutable (Principle I & test_aktivitas.py).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Equipment, Plant, ProductionLine
from app.models.maintenance import (
    ActivitySparePart,
    MaintenanceActivity,
    SparePart,
    WorkOrder,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchInstallation:
    """A record of sparepart installation carrying a specific batch number."""

    batch_number: str
    part_number: str
    part_name: str
    equipment_tag: str
    plant: str
    work_order_number: str
    installed_on: date | None


async def find_batch_installations(
    session: AsyncSession, batch_number: str
) -> list[BatchInstallation]:
    """Find all equipment and plants where spareparts from a batch were installed."""
    stmt = (
        select(
            ActivitySparePart.batch_number,
            SparePart.part_number,
            SparePart.name,
            Equipment.tag_number,
            Plant.name,
            WorkOrder.work_order_number,
            MaintenanceActivity.completed_at,
        )
        .join(SparePart, SparePart.id == ActivitySparePart.spare_part_id)
        .join(MaintenanceActivity, MaintenanceActivity.id == ActivitySparePart.activity_id)
        .join(WorkOrder, WorkOrder.id == MaintenanceActivity.work_order_id)
        .join(Equipment, Equipment.id == WorkOrder.equipment_id)
        .join(ProductionLine, ProductionLine.id == Equipment.production_line_id)
        .join(Plant, Plant.id == ProductionLine.plant_id)
        .where(ActivitySparePart.batch_number == batch_number)
        .order_by(MaintenanceActivity.completed_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        BatchInstallation(
            batch_number=r[0],
            part_number=r[1],
            part_name=r[2],
            equipment_tag=r[3],
            plant=r[4],
            work_order_number=r[5],
            installed_on=r[6].date() if r[6] else None,
        )
        for r in rows
    ]
