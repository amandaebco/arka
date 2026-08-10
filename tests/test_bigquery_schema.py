"""The mirror's schema is generated, so the generator is what needs testing.

These tests never touch BigQuery. They check the translation from SQLAlchemy
metadata to BigQuery schemas, which is where a migration of this shape goes
wrong: not in the load, but in a column that arrives with the wrong type and
reads back as null.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.bigquery import config, edges, traversal
from app.bigquery.schema import (
    UnmappedColumnType,
    all_tables,
    bigquery_type,
    schema_for,
    serialise,
    serialise_row,
)
from app.models.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def _column(table_name: str, column_name: str):
    return _table(table_name).columns[column_name]


class TestTypeMapping:
    def test_every_column_in_every_table_maps(self):
        """No table may reach BigQuery with a column the mapper cannot express.

        This is the test that makes the mirror trustworthy: it fails the moment
        somebody adds a column type nobody has decided how to store.
        """
        for table in all_tables():
            for column in table.columns:
                assert bigquery_type(column)

    @pytest.mark.parametrize(
        ("table", "column", "expected"),
        [
            ("failure_events", "id", "STRING"),
            ("failure_events", "equipment_id", "STRING"),
            ("failure_events", "started_at", "TIMESTAMP"),
            ("failure_events", "downtime_minutes", "INT64"),
            ("failure_events", "description", "STRING"),
            ("spare_parts", "static_criticality", "NUMERIC"),
            ("failure_event_causes", "is_primary", "BOOL"),
        ],
    )
    def test_representative_columns(self, table, column, expected):
        assert bigquery_type(_column(table, column)) == expected

    def test_uuid_beats_string(self):
        """UUID must not fall through to the String branch as a side effect."""
        assert bigquery_type(_column("plants", "id")) == "STRING"

    def test_unmapped_type_raises(self):
        from sqlalchemy import Column, LargeBinary, MetaData, Table

        t = Table("sementara", MetaData(), Column("blob", LargeBinary))
        with pytest.raises(UnmappedColumnType, match="sementara.blob"):
            bigquery_type(t.columns["blob"])


class TestSchemaShape:
    def test_column_names_and_order_are_preserved(self):
        table = _table("spare_parts")
        fields = schema_for(table)
        assert [f.name for f in fields] == [c.name for c in table.columns]

    def test_everything_is_nullable(self):
        """BigQuery enforces no constraints; a REQUIRED field only breaks loads."""
        for field in schema_for(_table("failure_events")):
            assert field.mode == "NULLABLE"

    def test_every_mapped_table_is_covered(self):
        """A guard on the count, so a new model cannot be added without a decision.

        Adding a table to the ORM and forgetting the mirror is silent: BigQuery
        simply never hears about it. This test turns that into a failure.
        """
        names = {t.name for t in all_tables()}
        assert len(names) == 39
        # The tables the detection layer actually reads, all present.
        assert {
            "plants",
            "production_lines",
            "equipment",
            "components",
            "failure_events",
            "failure_event_symptoms",
            "failure_event_causes",
            "symptoms",
            "causes",
            "work_orders",
            "work_order_failure_events",
            "spare_parts",
            "documents",
            "document_versions",
            "document_chunks",
        } <= names

    def test_parents_precede_children(self):
        order = [t.name for t in all_tables()]
        assert order.index("plants") < order.index("production_lines")
        assert order.index("equipment") < order.index("failure_events")
        assert order.index("failure_events") < order.index("failure_event_symptoms")


class TestSerialisation:
    def test_uuid_becomes_string(self):
        u = uuid.uuid4()
        assert serialise(u) == str(u)

    def test_decimal_stays_exact(self):
        """A Decimal routed through float would round the number ARKA argues from."""
        assert serialise(Decimal("0.3000")) == "0.3000"
        assert isinstance(serialise(Decimal("0.8667")), str)

    def test_datetime_and_date(self):
        assert serialise(datetime(2026, 8, 11, 9, 30, tzinfo=UTC)).startswith("2026-08-11T09:30")
        assert serialise(date(2026, 8, 11)) == "2026-08-11"

    def test_none_and_plain_values_pass_through(self):
        assert serialise(None) is None
        assert serialise("seal") == "seal"
        assert serialise(42) == 42
        assert serialise(True) is True

    def test_row_is_serialised_key_by_key(self):
        u = uuid.uuid4()
        row = serialise_row({"id": u, "n": 3, "at": date(2026, 8, 11), "kosong": None})
        assert row == {"id": str(u), "n": 3, "at": "2026-08-11", "kosong": None}


class TestEdgeList:
    def test_every_node_source_is_a_mirrored_table(self):
        names = {t.name for t in all_tables()}
        for _label, (table, _column) in edges.NODE_SOURCES.items():
            assert table in names

    def test_every_edge_endpoint_has_a_node_label(self):
        """An edge to a label with no node row would traverse into a nameless id."""
        labels = set(edges.NODE_SOURCES)
        for _t, _sc, src_label, _dc, dst_label, _e in edges.EDGE_SOURCES:
            assert src_label in labels
            assert dst_label in labels

    def test_every_edge_table_exists(self):
        """Every relationship is a real table, except the derived component pairs."""
        names = {t.name for t in all_tables()} | {edges.DERIVED_TABLE}
        for table, *_ in edges.EDGE_SOURCES:
            assert table in names

    def test_edge_columns_exist_on_their_table(self):
        """A mistyped column name would produce an empty edge type, not an error."""
        for table, src_col, _sl, dst_col, _dl, _e in edges.EDGE_SOURCES:
            if table == edges.DERIVED_TABLE:
                continue
            columns = {c.name for c in _table(table).columns}
            assert src_col in columns
            assert dst_col in columns

    def test_display_columns_exist(self):
        for _label, (table, column) in edges.NODE_SOURCES.items():
            assert column in {c.name for c in _table(table).columns}

    def test_edge_labels_are_distinct_per_pair(self):
        pairs = [(t, sc, dc, e) for t, sc, _sl, dc, _dl, e in edges.EDGE_SOURCES]
        assert len(pairs) == len(set(pairs))

    def test_supply_chain_edge_is_present(self):
        """DIPASOK_OLEH is what makes the four-hop supply-chain question reachable."""
        labels = {e[-1] for e in edges.EDGE_SOURCES}
        assert "DIPASOK_OLEH" in labels


class TestTraversal:
    def test_depth_is_capped(self):
        with pytest.raises(traversal.TooDeep):
            traversal.traverse("Equipment", "PLT-U/FIL-207", max_hops=traversal.MAX_HOPS + 1)

    def test_five_hops_is_within_the_cap(self):
        """The depth the supply-chain question needs must not be refused."""
        assert traversal.MAX_HOPS >= 5

    def test_sql_walks_both_directions(self):
        """Forward-only traversal dead-ends at spare parts after three hops."""
        sql = traversal._sql()
        assert "dua_arah" in sql
        assert "UNION ALL" in sql

    def test_sql_guards_against_cycles(self):
        assert "STRPOS" in traversal._sql()

    def test_sql_respects_the_hop_parameter(self):
        assert "j.hops < @max_hops" in traversal._sql()


class TestPathRendering:
    def _path(self, **kwargs):
        base = dict(
            target_id="x",
            target_label="Equipment",
            target_name="PLT-B/FIL-204",
            hops=2,
            edge_labels=("MEMILIKI_KOMPONEN", "DIPASOK_OLEH"),
            node_names=("PLT-U/FIL-207", "seal", "SP-SEAL-8801"),
        )
        return traversal.Path(**{**base, **kwargs})

    def test_sentence_names_every_hop(self):
        kalimat = self._path().as_sentence()
        assert kalimat == (
            "PLT-U/FIL-207 -[MEMILIKI_KOMPONEN]-> seal -[DIPASOK_OLEH]-> SP-SEAL-8801"
        )

    def test_reversed_step_is_marked(self):
        kalimat = self._path(
            edge_labels=("MEMILIKI_KOMPONEN", "DIPASOK_OLEH⁻¹"),
        ).as_sentence()
        assert "DIPASOK_OLEH⁻¹" in kalimat

    def test_single_node_path_renders(self):
        kalimat = self._path(edge_labels=(), node_names=("PLT-U/FIL-207",)).as_sentence()
        assert kalimat == "PLT-U/FIL-207"

    def test_empty_path_does_not_raise(self):
        assert self._path(edge_labels=(), node_names=()).as_sentence() == ""


class TestConfig:
    def test_defaults_to_the_canonical_mirror_not_the_old_copy(self, monkeypatch):
        """`arka_graph` holds the flattened demo copy and must not be the default."""
        monkeypatch.delenv("ARKA_BQ_DATASET", raising=False)
        assert config.dataset() == "arka"
        assert config.dataset() != "arka_graph"

    def test_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("ARKA_BQ_PROJECT", "proyek-lain")
        monkeypatch.setenv("ARKA_BQ_DATASET", "dataset-lain")
        assert config.dataset_ref() == "proyek-lain.dataset-lain"
        assert config.table_ref("plants") == "`proyek-lain.dataset-lain.plants`"
