import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.assets import Component, Equipment
from app.models.base import Base, TimestampMixin
from app.models.maintenance import WorkOrder


class Symptom(TimestampMixin, Base):
    __tablename__ = "symptoms"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)


class FailureMode(TimestampMixin, Base):
    __tablename__ = "failure_modes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)


class Cause(TimestampMixin, Base):
    __tablename__ = "causes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class FailureEvent(TimestampMixin, Base):
    __tablename__ = "failure_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'under_investigation', 'resolved', 'closed')",
            name="status",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="valid_time_range",
        ),
        CheckConstraint(
            "downtime_minutes IS NULL OR downtime_minutes >= 0",
            name="nonnegative_downtime",
        ),
        Index("ix_failure_events_equipment_id", "equipment_id"),
        Index("ix_failure_events_component_id", "component_id"),
        Index("ix_failure_events_started_at", "started_at"),
        Index("ix_failure_events_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"))
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    event_number: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downtime_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))

    equipment: Mapped[Equipment] = relationship()
    component: Mapped[Component | None] = relationship()
    symptom_links: Mapped[list["FailureEventSymptom"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )
    failure_mode_links: Mapped[list["FailureEventFailureMode"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )
    verified_cause_links: Mapped[list["FailureEventCause"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )
    damages: Mapped[list["Damage"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )
    work_order_links: Mapped[list["WorkOrderFailureEvent"]] = relationship(
        back_populates="failure_event", cascade="all, delete-orphan"
    )


class FailureEventSymptom(Base):
    __tablename__ = "failure_event_symptoms"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity",
        ),
    )

    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE"), primary_key=True
    )
    symptom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symptoms.id", ondelete="RESTRICT"), primary_key=True
    )
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(30))

    failure_event: Mapped[FailureEvent] = relationship(back_populates="symptom_links")
    symptom: Mapped[Symptom] = relationship()


class FailureEventFailureMode(Base):
    __tablename__ = "failure_event_failure_modes"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE"), primary_key=True
    )
    failure_mode_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_modes.id", ondelete="RESTRICT"), primary_key=True
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())

    failure_event: Mapped[FailureEvent] = relationship(back_populates="failure_mode_links")
    failure_mode: Mapped[FailureMode] = relationship()


class FailureEventCause(Base):
    __tablename__ = "failure_event_causes"
    __table_args__ = (
        UniqueConstraint(
            "failure_event_id", "cause_id", name="uq_failure_event_causes_event_cause"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE")
    )
    cause_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("causes.id", ondelete="RESTRICT"))
    verification_method: Mapped[str] = mapped_column(String(100))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())

    failure_event: Mapped[FailureEvent] = relationship(back_populates="verified_cause_links")
    cause: Mapped[Cause] = relationship()


class Damage(TimestampMixin, Base):
    __tablename__ = "damages"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity",
        ),
        Index("ix_damages_failure_event_id", "failure_event_id"),
        Index("ix_damages_component_id", "component_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT")
    )
    damage_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    failure_event: Mapped[FailureEvent] = relationship(back_populates="damages")
    component: Mapped[Component | None] = relationship()


class WorkOrderFailureEvent(Base):
    __tablename__ = "work_order_failure_events"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('responds_to', 'follow_up')",
            name="relationship_type",
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), primary_key=True
    )
    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE"), primary_key=True
    )
    relationship_type: Mapped[str] = mapped_column(String(30))

    work_order: Mapped[WorkOrder] = relationship()
    failure_event: Mapped[FailureEvent] = relationship(back_populates="work_order_links")
