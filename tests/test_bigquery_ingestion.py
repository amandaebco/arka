"""Unit tests for direct BigQuery ingestion connector (Feature 007)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.bigquery.ingestion import ingest_canonical_dataset, load_table_records


class TestLoadTableRecords:
    def test_empty_records_returns_zero(self):
        assert load_table_records("dummy_table", []) == 0

    @patch("google.cloud.bigquery.Client")
    def test_loads_records_via_load_table_from_json(self, mock_client_cls):
        mock_client = MagicMock()
        mock_job = MagicMock()
        mock_client.load_table_from_json.return_value = mock_job
        mock_client_cls.return_value = mock_client

        records = [{"id": "1", "name": "Test Record"}]
        count = load_table_records("test_table", records)

        assert count == 1
        assert mock_client.load_table_from_json.called
        mock_job.result.assert_called_once()


class TestIngestCanonicalDataset:
    @patch("app.bigquery.edges.build")
    @patch("app.bigquery.ingestion.load_table_records")
    def test_ingests_and_rebuilds_graph(self, mock_load, mock_edges_build):
        mock_load.return_value = 5
        mock_edges_build.return_value = (100, 200)

        dataset = {"plants": [{"id": "p1"}], "equipment": [{"id": "e1"}]}
        result = ingest_canonical_dataset(dataset, rebuild_graph=True)

        assert result["plants"] == 5
        assert result["equipment"] == 5
        assert result["_graph_nodes"] == 100
        assert result["_graph_edges"] == 200
        mock_edges_build.assert_called_once()
