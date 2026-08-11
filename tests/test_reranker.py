"""Unit tests for the reranking layer in semantic retrieval."""

from __future__ import annotations

from app.retrieval.reranker import calculate_keyword_overlap, rerank_hits
from app.retrieval.vector_store import SemanticHit


def _hit(doc_id: str, title: str, content: str, similarity: float) -> SemanticHit:
    return SemanticHit(
        document_id=doc_id,
        title=title,
        document_type="inspection_report",
        content=content,
        page_number=1,
        similarity=similarity,
    )


class TestKeywordOverlap:
    def test_matches_equipment_and_component_keywords(self):
        question = "apa penyebab seal bocor di PLT-U/FIL-207?"
        title = "Laporan Inspeksi PLT-U/FIL-207"
        content = "Ditemukan kebocoran seal akibat degradasi material."
        overlap = calculate_keyword_overlap(question, content, title)
        assert overlap > 0.5

    def test_empty_question_returns_zero(self):
        assert calculate_keyword_overlap("", "content", "title") == 0.0

    def test_unrelated_text_has_low_overlap(self):
        question = "apa penyebab seal bocor?"
        title = "Laporan Keuangan"
        content = "Perusahaan mencatatkan laba bersih minggu ini."
        overlap = calculate_keyword_overlap(question, content, title)
        assert overlap == 0.0


class TestRerankHits:
    def test_boosts_relevant_in_domain_hits(self):
        question = "kenapa seal bocor di mesin filler PLT-U/FIL-207?"
        hits = [
            _hit("DOC-1", "Inspeksi Filler", "Terjadi kebocoran seal di PLT-U/FIL-207.", 0.58),
            _hit("DOC-2", "Resep Makanan", "Rendang padang dimasak dengan santan.", 0.59),
        ]
        reranked = rerank_hits(question, hits)
        assert len(reranked) == 1
        assert reranked[0].document_id == "DOC-1"

    def test_empty_hits_returns_empty(self):
        assert rerank_hits("pertanyaan", []) == []

    def test_relative_margin_prunes_distant_outliers(self):
        question = "apa penyebab vibrasi bearing?"
        hits = [
            _hit("DOC-A", "Laporan Vibrasi", "Vibrasi tinggi pada bearing motor.", 0.85),
            _hit("DOC-B", "Catatan Umum", "Informasi jadwal rapat bulanan.", 0.51),
        ]
        reranked = rerank_hits(question, hits)
        assert len(reranked) == 1
        assert reranked[0].document_id == "DOC-A"
