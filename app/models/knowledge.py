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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.assets import Component, Equipment
from app.models.base import Base, TimestampMixin
from app.models.reliability import Cause, FailureEvent


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('technician_note', 'inspection_report', 'manual', "
            "'datasheet', 'rcps', 'fmea', 'other')",
            name="type",
        ),
        UniqueConstraint(
            "source_system",
            "source_document_id",
            name="uq_documents_source_document",
        ),
        Index("ix_documents_document_type", "document_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_id: Mapped[str] = mapped_column(String(100), unique=True)
    source_system: Mapped[str] = mapped_column(String(100))
    source_document_id: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(255))
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_version",
        ),
        UniqueConstraint(
            "document_id",
            "content_hash",
            name="uq_document_versions_document_hash",
        ),
        Index("ix_document_versions_document_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(128))
    mime_type: Mapped[str] = mapped_column(String(100))
    storage_uri: Mapped[str | None] = mapped_column(String(1000))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="nonnegative_index"),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="valid_offsets",
        ),
        UniqueConstraint(
            "document_version_id",
            "chunk_index",
            name="uq_document_chunks_version_index",
        ),
        Index("ix_document_chunks_document_version_id", "document_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128))
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)

    document_version: Mapped[DocumentVersion] = relationship(back_populates="chunks")
    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="document_chunk", cascade="all, delete-orphan"
    )


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="valid_offsets",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "evidence_format IN ('text', 'table', 'image')",
            name="format",
        ),
        Index("ix_evidence_document_chunk_id", "document_chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE")
    )
    evidence_type: Mapped[str] = mapped_column(String(100))
    quote_text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    extraction_method: Mapped[str] = mapped_column(String(100))
    extractor_version: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    evidence_format: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'text'")
    )
    bounding_box: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    document_chunk: Mapped[DocumentChunk] = relationship(back_populates="evidence_items")
    claim_links: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "claim_type IN ("
            "'observation', 'measurement', 'negative_finding', 'symptom', "
            "'failure_mode', 'damage', 'probable_cause', 'risk', "
            "'diagnostic_result', 'recommended_activity', 'executed_activity', "
            "'operational_constraint')",
            name="type",
        ),
        CheckConstraint(
            "assertion_status IN ("
            "'observed', 'suspected', 'confirmed', 'negated', "
            "'recommended', 'executed')",
            name="assertion_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "review_status IN ('unreviewed', 'accepted', 'rejected')",
            name="review_status",
        ),
        Index("ix_claims_failure_event_id", "failure_event_id"),
        Index("ix_claims_equipment_id", "equipment_id"),
        Index("ix_claims_component_id", "component_id"),
        Index("ix_claims_proposed_cause_id", "proposed_cause_id"),
        Index("ix_claims_review_status", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    failure_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("failure_events.id", ondelete="SET NULL")
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT")
    )
    proposed_cause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("causes.id", ondelete="RESTRICT")
    )
    source_key: Mapped[str] = mapped_column(String(128), unique=True)
    claim_type: Mapped[str] = mapped_column(String(50))
    assertion_status: Mapped[str] = mapped_column(String(30))
    statement: Mapped[str] = mapped_column(Text)
    subject_text: Mapped[str | None] = mapped_column(String(500))
    predicate: Mapped[str | None] = mapped_column(String(100))
    object_text: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    engineering_unit: Mapped[str | None] = mapped_column(String(50))
    source_section: Mapped[str | None] = mapped_column(String(100))
    attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    review_status: Mapped[str] = mapped_column(String(30), server_default=text("'unreviewed'"))
    extraction_method: Mapped[str] = mapped_column(String(100))
    extractor_version: Mapped[str | None] = mapped_column(String(255))

    failure_event: Mapped[FailureEvent | None] = relationship()
    equipment: Mapped[Equipment | None] = relationship()
    component: Mapped[Component | None] = relationship()
    proposed_cause: Mapped[Cause | None] = relationship()
    evidence_links: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ClaimReview"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )

    claim: Mapped[Claim] = relationship(back_populates="evidence_links")
    evidence: Mapped[Evidence] = relationship(back_populates="claim_links")


class ClaimReview(Base):
    __tablename__ = "claim_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'rejected')",
            name="decision",
        ),
        Index("ix_claim_reviews_claim_id", "claim_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    reviewer: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    claim: Mapped[Claim] = relationship(back_populates="reviews")
