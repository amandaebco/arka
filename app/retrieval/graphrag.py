"""GraphRAG — retrieval that reads the graph and the documents together.

Text search knows what was written. A graph knows what is connected. Reliability
questions almost always need both: "which plants run the part that failed here"
is a traversal, "what did they actually do about it" is a sentence in a report,
and the useful answer is the two joined.

Retrieving them separately and pasting the results together is not the same
thing. The join happens here: semantic hits name documents, documents belong to
cases, cases belong to equipment and plants — so a match on a sentence pulls in
the structure around it, and a traversal pulls in the sentences that explain it.

Everything in this module is deterministic. It decides *what* a question is
about and *what* to fetch; it never decides what the answer is.

Traceability: spec 003 FR-002, FR-004 · tasks T015.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from google.cloud import bigquery

from app.bigquery import config
from app.retrieval.vector_store import SemanticHit, search

logger = logging.getLogger(__name__)

# A context that grows without limit stops being context. Beyond this, the
# earlier hits crowd out the later ones and nobody can tell which sentence the
# answer rested on.
MAX_CHUNKS = 6
MAX_CASES = 8


@dataclass(frozen=True)
class GraphFact:
    """One structural fact pulled in around a document hit."""

    equipment_tag: str
    plant: str
    status: str
    occurred_on: str | None
    cause_name: str | None


@dataclass(frozen=True)
class RetrievedContext:
    """What a question pulled in, and where every piece came from."""

    question: str
    chunks: list[SemanticHit] = field(default_factory=list)
    facts: list[GraphFact] = field(default_factory=list)
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.chunks and not self.facts

    @property
    def plants(self) -> list[str]:
        return sorted({f.plant for f in self.facts})

    @property
    def citations(self) -> list[str]:
        return sorted({c.document_id for c in self.chunks})


def _client() -> bigquery.Client:
    return bigquery.Client(project=config.project())


def _facts_for(terms: list[str]) -> list[GraphFact]:
    """Walk equipment → failure event → cause for the question's terms.

    Written as joins over the canonical mirror rather than `GRAPH_EXPAND`. The
    property graph earns its keep on questions shaped like traversals — which
    plants run a part, which technicians touched a cause — where the number of
    hops is the question. This one is a filter over three tables that happen to
    be connected, and saying so in SQL is both cheaper and easier to check.
    """
    if not terms:
        return []

    sql = f"""
    SELECT e.tag_number AS equipment_tag, p.name AS plant, f.status,
           CAST(DATE(f.started_at) AS STRING) AS occurred_on,
           ANY_VALUE(cs.name) AS cause_name
    FROM {config.table_ref("failure_events")} f
    JOIN {config.table_ref("equipment")} e ON e.id = f.equipment_id
    JOIN {config.table_ref("production_lines")} l ON l.id = e.production_line_id
    JOIN {config.table_ref("plants")} p ON p.id = l.plant_id
    LEFT JOIN {config.table_ref("failure_event_causes")} fc ON fc.failure_event_id = f.id
    LEFT JOIN {config.table_ref("causes")} cs ON cs.id = fc.cause_id
    WHERE EXISTS (
      SELECT 1 FROM UNNEST(@terms) t
      WHERE LOWER(e.tag_number) LIKE CONCAT('%', LOWER(t), '%')
         OR LOWER(p.name) LIKE CONCAT('%', LOWER(t), '%')
         OR LOWER(IFNULL(cs.name, '')) LIKE CONCAT('%', LOWER(t), '%')
    )
    GROUP BY 1, 2, 3, 4
    ORDER BY occurred_on DESC
    LIMIT @limit
    """
    job = _client().query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("terms", "STRING", terms),
                bigquery.ScalarQueryParameter("limit", "INT64", MAX_CASES),
            ]
        ),
    )
    return [
        GraphFact(
            equipment_tag=r.equipment_tag,
            plant=r.plant,
            status=r.status,
            occurred_on=str(r.occurred_on) if r.occurred_on else None,
            cause_name=r.cause_name,
        )
        for r in job.result()
    ]


def _terms_from(question: str, hits: list[SemanticHit]) -> list[str]:
    """Pick the terms worth traversing on.

    Taken from the retrieved documents rather than from the question itself: the
    engineer's wording is exactly what does not match the records, which is why
    semantic search ran first. The documents supply the vocabulary the graph
    actually uses.
    """
    terms: set[str] = set()
    for kata in question.replace(",", " ").split():
        bersih = kata.strip(".?!:;()").lower()
        # Plant and equipment identifiers are the only question tokens worth
        # matching directly; ordinary words would match everything.
        if bersih.startswith("plt-") or bersih.startswith("pabrik"):
            terms.add(bersih)
    for hit in hits:
        for kandidat in ("seal", "torsi", "bearing", "katup", "nozel"):
            if kandidat in hit.content.lower():
                terms.add(kandidat)
    return sorted(terms)


def retrieve(question: str, limit: int = MAX_CHUNKS) -> RetrievedContext:
    """Gather document and graph context for one question.

    Returns an empty context rather than a weak one when nothing clears the
    similarity threshold. An answer built on nothing is worse than no answer,
    and the calling agent is instructed to say so plainly.
    """
    hits = search(question, limit=limit + 2)
    truncated = len(hits) > limit
    hits = hits[:limit]

    facts = _facts_for(_terms_from(question, hits))
    logger.info(
        "retrieved %d chunks and %d facts for: %s", len(hits), len(facts), question[:60]
    )
    return RetrievedContext(
        question=question, chunks=hits, facts=facts, truncated=truncated
    )


def as_prompt_context(context: RetrievedContext) -> str:
    """Render the context for a model, with every claim still attributable.

    Citations travel with the text rather than in a separate list, because a
    model asked to answer from a wall of prose will cite whatever is nearest.
    """
    if context.is_empty:
        return "TIDAK ADA KONTEKS. Pengetahuan yang tersedia tidak menjawab pertanyaan ini."

    baris: list[str] = []
    if context.facts:
        baris.append("FAKTA DARI GRAPH:")
        for f in context.facts:
            penyebab = f" · penyebab terverifikasi: {f.cause_name}" if f.cause_name else ""
            baris.append(
                f"- {f.equipment_tag} di {f.plant} · status {f.status}"
                f" · {f.occurred_on or 'tanggal tidak tercatat'}{penyebab}"
            )
    if context.chunks:
        baris.append("\nKUTIPAN DOKUMEN:")
        for c in context.chunks:
            halaman = f", hlm. {c.page_number}" if c.page_number else ""
            baris.append(f"- [{c.document_id}{halaman}] {c.title}\n  {c.content}")
    if context.truncated:
        baris.append("\nCATATAN: hasil dipotong oleh batas konteks.")
    return "\n".join(baris)
