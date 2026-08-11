import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.assets import Component, Equipment
from app.models.base import Base, TimestampMixin


class Technician(TimestampMixin, Base):
    __tablename__ = "technicians"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    employee_number: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    specialization: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30))

    activity_assignments: Mapped[list["ActivityTechnician"]] = relationship(
        back_populates="technician", cascade="all, delete-orphan"
    )


class SparePart(TimestampMixin, Base):
    """Sparepart beserta atribut rantai pasok.

    `static_criticality` adalah nilai yang tertulis di master data — ditetapkan
    sekali saat pendaftaran material dan nyaris tidak pernah ditinjau ulang.
    Kekritisan dinamis ARKA dihitung terpisah dan tidak disimpan di sini;
    yang bernilai justru **selisih** antara keduanya.
    """

    __tablename__ = "spare_parts"
    __table_args__ = (
        CheckConstraint(
            "static_criticality IS NULL OR (static_criticality >= 0 AND static_criticality <= 1)",
            name="static_criticality_range",
        ),
        CheckConstraint(
            "lead_time_weeks IS NULL OR lead_time_weeks >= 0",
            name="nonnegative_lead_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    part_number: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    # Jenis komponen yang dilayani part ini. Tanpa tautan ini, pemilihan part
    # untuk sebuah temuan hanya bisa menebak dari kemiripan nama — dan tebakan
    # nama adalah cara paling halus untuk salah menautkan biaya ke aset.
    component_type: Mapped[str | None] = mapped_column(String(100))

    # Rantai pasok — dasar komponen `supply_risk` pada kekritisan dinamis.
    static_criticality: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    lead_time_weeks: Mapped[int | None] = mapped_column(Integer)
    vendor_count: Mapped[int | None] = mapped_column(Integer)
    primary_vendor: Mapped[str | None] = mapped_column(String(255))

    activity_usages: Mapped[list["ActivitySparePart"]] = relationship(
        back_populates="spare_part", cascade="all, delete-orphan"
    )


class WorkOrder(TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint(
            "work_order_type IN ('corrective', 'preventive', 'inspection', 'unclassified')",
            name="type",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical', 'unclassified')",
            name="priority",
        ),
        CheckConstraint(
            "status IN ('created', 'approved', 'in_progress', 'completed', 'cancelled')",
            name="status",
        ),
        Index("ix_work_orders_equipment_id", "equipment_id"),
        Index("ix_work_orders_status", "status"),
        Index("ix_work_orders_opened_at", "opened_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"))
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    work_order_number: Mapped[str] = mapped_column(String(100), unique=True)
    work_order_type: Mapped[str] = mapped_column(String(30))
    priority: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))
    source_order_type: Mapped[str | None] = mapped_column(String(50))
    source_priority: Mapped[str | None] = mapped_column(String(50))
    source_user_status: Mapped[str | None] = mapped_column(String(100))
    source_system_status: Mapped[str | None] = mapped_column(String(500))

    equipment: Mapped[Equipment] = relationship()
    activities: Mapped[list["MaintenanceActivity"]] = relationship(
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="MaintenanceActivity.sequence_number",
    )


class MaintenanceNotification(TimestampMixin, Base):
    __tablename__ = "maintenance_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    notification_number: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))


class WorkOrderNotification(Base):
    __tablename__ = "work_order_notifications"
    __table_args__ = (Index("ix_work_order_notifications_notification_id", "notification_id"),)

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), primary_key=True
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_notifications.id", ondelete="CASCADE"), primary_key=True
    )


class NotificationConceptLink(TimestampMixin, Base):
    __tablename__ = "notification_concept_links"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('affects_part','reports_damage','has_cause')",
            name="type",
        ),
        CheckConstraint(
            "review_status IN ('unreviewed','accepted','rejected')", name="review_status"
        ),
        UniqueConstraint(
            "notification_id",
            "source_item_id",
            "relationship_type",
            name="uq_notification_concept_source_relation",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_notifications.id", ondelete="CASCADE")
    )
    semantic_concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_concepts.id", ondelete="RESTRICT")
    )
    # Sisa brownfield: dulu menunjuk `reference.catalog_codes`, master kode dari
    # jalur ETL. ARKA tidak punya ETL — data sintetis ditulis langsung ke tabel
    # kanonik — jadi skema `reference` tidak pernah ada. Kolomnya dilepas;
    # `source_item_id` sudah cukup melacak asal usulan pemetaan.
    source_item_id: Mapped[uuid.UUID] = mapped_column()
    relationship_type: Mapped[str] = mapped_column(String(50))
    review_status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaintenanceActivity(TimestampMixin, Base):
    __tablename__ = "maintenance_activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("sequence_number > 0", name="positive_sequence"),
        UniqueConstraint(
            "work_order_id",
            "sequence_number",
            name="uq_maintenance_activities_work_order_sequence",
        ),
        Index("ix_maintenance_activities_work_order_id", "work_order_id"),
        Index("ix_maintenance_activities_activity_type", "activity_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE")
    )
    activity_code: Mapped[str] = mapped_column(String(100))
    activity_type: Mapped[str] = mapped_column(String(100))
    sequence_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))

    work_order: Mapped[WorkOrder] = relationship(back_populates="activities")
    technician_assignments: Mapped[list["ActivityTechnician"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )
    spare_part_usages: Mapped[list["ActivitySparePart"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )
    targets: Mapped[list["ActivityTarget"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )


class ActivityTechnician(Base):
    __tablename__ = "activity_technicians"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    technician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("technicians.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(100))

    activity: Mapped[MaintenanceActivity] = relationship(back_populates="technician_assignments")
    technician: Mapped[Technician] = relationship(back_populates="activity_assignments")


class ActivitySparePart(Base):
    __tablename__ = "activity_spare_parts"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spare_parts.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(30))
    batch_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    activity: Mapped[MaintenanceActivity] = relationship(back_populates="spare_part_usages")
    spare_part: Mapped[SparePart] = relationship(back_populates="activity_usages")


class ActivityTarget(Base):
    __tablename__ = "activity_targets"
    __table_args__ = (
        CheckConstraint(
            "((equipment_id IS NOT NULL)::integer + (component_id IS NOT NULL)::integer) = 1",
            name="exactly_one_asset",
        ),
        UniqueConstraint(
            "activity_id",
            "equipment_id",
            name="uq_activity_targets_activity_equipment",
        ),
        UniqueConstraint(
            "activity_id",
            "component_id",
            name="uq_activity_targets_activity_component",
        ),
        Index("ix_activity_targets_equipment_id", "equipment_id"),
        Index("ix_activity_targets_component_id", "component_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_activities.id", ondelete="CASCADE")
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT")
    )

    activity: Mapped[MaintenanceActivity] = relationship(back_populates="targets")
    equipment: Mapped[Equipment | None] = relationship()
    component: Mapped[Component | None] = relationship()
