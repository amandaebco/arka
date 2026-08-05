import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Plant(TimestampMixin, Base):
    __tablename__ = "plants"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    production_lines: Mapped[list["ProductionLine"]] = relationship(back_populates="plant")


class ProductionLine(TimestampMixin, Base):
    __tablename__ = "production_lines"
    __table_args__ = (
        UniqueConstraint("plant_id", "code", name="uq_production_lines_plant_code"),
        Index("ix_production_lines_plant_id", "plant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id", ondelete="RESTRICT"))
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    plant: Mapped[Plant] = relationship(back_populates="production_lines")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="production_line")


class Equipment(TimestampMixin, Base):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'retired')",
            name="status",
        ),
        Index("ix_equipment_production_line_id", "production_line_id"),
        Index("ix_equipment_equipment_type", "equipment_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    production_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_lines.id", ondelete="RESTRICT")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    tag_number: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    equipment_type: Mapped[str] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    commissioned_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))

    production_line: Mapped[ProductionLine] = relationship(back_populates="equipment")
    components: Mapped[list["Component"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    identifiers: Mapped[list["AssetIdentifier"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )


class Component(TimestampMixin, Base):
    __tablename__ = "components"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'retired')",
            name="status",
        ),
        UniqueConstraint(
            "equipment_id",
            "tag_number",
            name="uq_components_equipment_tag_number",
        ),
        Index("ix_components_equipment_id", "equipment_id"),
        Index("ix_components_component_type", "component_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    tag_number: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    component_type: Mapped[str] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30))

    equipment: Mapped[Equipment] = relationship(back_populates="components")
    identifiers: Mapped[list["AssetIdentifier"]] = relationship(
        back_populates="component", cascade="all, delete-orphan"
    )


class AssetIdentifier(TimestampMixin, Base):
    __tablename__ = "asset_identifiers"
    __table_args__ = (
        CheckConstraint(
            "((equipment_id IS NOT NULL)::integer + (component_id IS NOT NULL)::integer) = 1",
            name="exactly_one_asset",
        ),
        UniqueConstraint(
            "source_system",
            "identifier_type",
            "identifier_value",
            name="uq_asset_identifiers_source_type_value",
        ),
        Index("ix_asset_identifiers_equipment_id", "equipment_id"),
        Index("ix_asset_identifiers_component_id", "component_id"),
        Index("ix_asset_identifiers_value", "identifier_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE")
    )
    source_system: Mapped[str] = mapped_column(String(100))
    identifier_type: Mapped[str] = mapped_column(String(100))
    identifier_value: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    equipment: Mapped[Equipment | None] = relationship(back_populates="identifiers")
    component: Mapped[Component | None] = relationship(back_populates="identifiers")
