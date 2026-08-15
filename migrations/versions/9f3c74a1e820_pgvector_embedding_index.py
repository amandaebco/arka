"""pgvector embedding index

Moves semantic search off BigQuery `VECTOR_SEARCH` and onto pgvector, so the
retrieval layer can run with no GCP dependency at all.

⚠️ No HNSW or IVFFlat index here, deliberately: pgvector caps its indexes at
2,000 dimensions while `gemini-embedding-2` returns 3,072. Across 104 chunks a
sequential scan finishes in milliseconds. Should the corpus grow into the tens
of thousands, the answer is a smaller embedding via `output_dimensionality` —
not an index the extension will refuse to build.

Revision ID: 9f3c74a1e820
Revises: 2a82d91bc802
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3c74a1e820"
down_revision: str | None = "2a82d91bc802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIMENSION = 3072


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks_embedded",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float()), nullable=False),
        # The model name is stored per row. Vectors from two models are not
        # comparable, and an equal dimension hides that rather than excusing it:
        # `text-embedding-3-large` also returns 3,072. Without this column a
        # mixed index is indistinguishable from a healthy one -- the search still
        # succeeds, and every result is meaningless.
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks_embedded")),
    )

    # The vector column goes in through raw SQL: `vector` belongs to pgvector,
    # not to SQLAlchemy's built-in types.
    op.execute("ALTER TABLE document_chunks_embedded DROP COLUMN embedding")
    op.execute(
        "ALTER TABLE document_chunks_embedded "
        f"ADD COLUMN embedding vector({DIMENSION}) NOT NULL"
    )

    op.create_index(
        op.f("ix_document_chunks_embedded_document_id"),
        "document_chunks_embedded",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_chunks_embedded_document_id"), table_name="document_chunks_embedded"
    )
    op.drop_table("document_chunks_embedded")
