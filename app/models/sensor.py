import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.assets import Component, Equipment
from app.models.base import Base, TimestampMixin
from app.models.reliability import FailureEvent, Symptom


class Sensor(TimestampMixin, Base):
    __tablename__ = "sensors"
    __table_args__ = (
        CheckConstraint(
            "((equipment_id IS NOT NULL)::integer + (component_id IS NOT NULL)::integer) = 1",
            name="exactly_one_asset",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'retired')",
            name="status",
        ),
        Index("ix_sensors_equipment_id", "equipment_id"),
        Index("ix_sensors_component_id", "component_id"),
        Index("ix_sensors_sensor_type", "sensor_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    tag_name: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    sensor_type: Mapped[str] = mapped_column(String(100))
    engineering_unit: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))

    equipment: Mapped[Equipment | None] = relationship()
    component: Mapped[Component | None] = relationship()
    observations: Mapped[list["Observation"]] = relationship(
        back_populates="sensor", cascade="all, delete-orphan"
    )
    alarms: Mapped[list["Alarm"]] = relationship(
        back_populates="sensor", cascade="all, delete-orphan"
    )


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "quality IN ('good', 'uncertain', 'bad')",
            name="quality",
        ),
        UniqueConstraint(
            "sensor_id",
            "observed_at",
            name="uq_observations_sensor_time",
        ),
        Index("ix_observations_sensor_time", "sensor_id", "observed_at"),
        Index("ix_observations_observed_at", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    engineering_unit: Mapped[str] = mapped_column(String(50))
    quality: Mapped[str] = mapped_column(String(30))
    source_record_id: Mapped[str | None] = mapped_column(String(255))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )

    sensor: Mapped[Sensor] = relationship(back_populates="observations")


class Alarm(TimestampMixin, Base):
    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity",
        ),
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'cleared')",
            name="status",
        ),
        CheckConstraint(
            "cleared_at IS NULL OR cleared_at >= triggered_at",
            name="valid_time_range",
        ),
        Index("ix_alarms_sensor_id", "sensor_id"),
        Index("ix_alarms_triggered_at", "triggered_at"),
        Index("ix_alarms_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sensors.id", ondelete="RESTRICT"))
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    alarm_code: Mapped[str] = mapped_column(String(100))
    alarm_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str] = mapped_column(String(255))

    sensor: Mapped[Sensor] = relationship(back_populates="alarms")
    symptom_links: Mapped[list["AlarmSymptom"]] = relationship(
        back_populates="alarm", cascade="all, delete-orphan"
    )
    failure_event_links: Mapped[list["AlarmFailureEvent"]] = relationship(
        back_populates="alarm", cascade="all, delete-orphan"
    )


class AlarmSymptom(Base):
    __tablename__ = "alarm_symptoms"

    alarm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alarms.id", ondelete="CASCADE"), primary_key=True
    )
    symptom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symptoms.id", ondelete="RESTRICT"), primary_key=True
    )

    alarm: Mapped[Alarm] = relationship(back_populates="symptom_links")
    symptom: Mapped[Symptom] = relationship()


class AlarmFailureEvent(Base):
    __tablename__ = "alarm_failure_events"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('preceded', 'occurred_during')",
            name="relationship_type",
        ),
    )

    alarm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alarms.id", ondelete="CASCADE"), primary_key=True
    )
    failure_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_events.id", ondelete="CASCADE"), primary_key=True
    )
    relationship_type: Mapped[str] = mapped_column(String(30))

    alarm: Mapped[Alarm] = relationship(back_populates="failure_event_links")
    failure_event: Mapped[FailureEvent] = relationship()


class OperatingState(TimestampMixin, Base):
    __tablename__ = "operating_states"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)


class EquipmentOperatingState(Base):
    __tablename__ = "equipment_operating_states"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="valid_time_range",
        ),
        UniqueConstraint(
            "equipment_id",
            "started_at",
            name="uq_equipment_operating_states_equipment_start",
        ),
        Index(
            "ix_equipment_operating_states_equipment_time",
            "equipment_id",
            "started_at",
            "ended_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    operating_state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operating_states.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_system: Mapped[str] = mapped_column(String(100))
    source_record_id: Mapped[str | None] = mapped_column(String(255))

    equipment: Mapped[Equipment] = relationship()
    operating_state: Mapped[OperatingState] = relationship()
