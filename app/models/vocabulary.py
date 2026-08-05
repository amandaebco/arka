import uuid

from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SemanticConcept(TimestampMixin, Base):
    __tablename__ = "semantic_concepts"
    __table_args__ = (
        CheckConstraint(
            "concept_type IN ('activity', 'component_type', 'damage', 'cause')",
            name="type",
        ),
        UniqueConstraint("concept_type", "normalized_label", name="uq_semantic_concept_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    concept_type: Mapped[str] = mapped_column(String(50))
    preferred_label: Mapped[str] = mapped_column(String(1000))
    normalized_label: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
