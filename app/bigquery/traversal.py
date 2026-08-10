"""Multi-hop traversal over the edge list, with a recursive CTE.

This is what replaces `GRAPH_EXPAND`. Depth is a parameter rather than a
property of the schema, so four and five hops are the same query as two, and
the path is returned as data — every intermediate node and the edge label that
justified each step.

That last part is the point. A traversal that returns only its destination
asks to be trusted; one that returns its path can be checked. ARKA's whole
credibility argument rests on a reviewer being able to follow the reasoning,
and a hop nobody can see is indistinguishable from a hop nobody took.

Cycle protection is a string containment test rather than an array membership
test: BigQuery's recursive term will not accept a subquery, and `STRPOS` over
a delimited trace says the same thing with a scalar function.

Edges are walked in **both** directions, and a reversed step is labelled with a
`⁻¹` suffix so the path still reads honestly. Direction in the edge list runs
the way an explanation runs — Component → SparePart means "this component is
supplied by that part" — but the question the supply-chain layer exists to
answer runs the other way: given a part, what else uses it. Walking forward
only, every route dead-ends at a spare part after three hops. The four- and
five-hop findings are all of the form "out to a shared part, then back down
into another plant", and they are unreachable without the reverse step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google.cloud import bigquery

from app.bigquery import config
from app.bigquery.edges import EDGE_TABLE, NODE_TABLE

logger = logging.getLogger(__name__)

# Beyond this the result stops being an explanation and becomes a census: in a
# connected estate almost everything is reachable from almost everything else
# given enough hops, and a path nobody can read supports no argument.
MAX_HOPS = 6


@dataclass(frozen=True)
class Path:
    """One route through the graph, with every step it took."""

    target_id: str
    target_label: str
    target_name: str | None
    hops: int
    edge_labels: tuple[str, ...]
    node_names: tuple[str, ...]

    def as_sentence(self) -> str:
        """The path as a line a reviewer can read against the graph."""
        bagian = [self.node_names[0]] if self.node_names else []
        for edge, node in zip(self.edge_labels, self.node_names[1:], strict=False):
            bagian.append(f"-[{edge}]-> {node}")
        return " ".join(bagian)


class TooDeep(ValueError):
    """A depth past what a readable path can carry."""


def _sql() -> str:
    edges = config.table_ref(EDGE_TABLE)
    nodes = config.table_ref(NODE_TABLE)
    return f"""
    WITH RECURSIVE
    dua_arah AS (
      SELECT source_id, target_id, edge_label, target_label FROM {edges}
      UNION ALL
      SELECT target_id, source_id, CONCAT(edge_label, '⁻¹'), source_label FROM {edges}
    ),
    awal AS (
      SELECT n.id, n.label, n.name
      FROM {nodes} n
      WHERE n.label = @start_label AND n.name = @start_name
    ),
    jalur AS (
      SELECT a.id AS target_id, a.label AS target_label, 0 AS hops,
             CONCAT('|', a.id, '|') AS trace,
             CAST([] AS ARRAY<STRING>) AS edge_labels,
             [a.name] AS node_names
      FROM awal a

      UNION ALL

      SELECT e.target_id, e.target_label, j.hops + 1,
             CONCAT(j.trace, e.target_id, '|'),
             ARRAY_CONCAT(j.edge_labels, [e.edge_label]),
             ARRAY_CONCAT(j.node_names, [IFNULL(n.name, e.target_id)])
      FROM jalur j
      JOIN dua_arah e ON e.source_id = j.target_id
      LEFT JOIN {nodes} n ON n.id = e.target_id AND n.label = e.target_label
      WHERE j.hops < @max_hops
        AND STRPOS(j.trace, CONCAT('|', e.target_id, '|')) = 0
    )
    SELECT j.target_id, j.target_label, j.hops, j.edge_labels, j.node_names,
           ANY_VALUE(n.name) AS target_name
    FROM jalur j
    LEFT JOIN {nodes} n ON n.id = j.target_id AND n.label = j.target_label
    WHERE j.hops > 0
      AND (@only_label IS NULL OR j.target_label = @only_label)
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY j.hops, j.target_label, target_name
    """


def traverse(
    start_label: str,
    start_name: str,
    *,
    max_hops: int = 4,
    only_label: str | None = None,
    client: bigquery.Client | None = None,
) -> list[Path]:
    """Walk outward from one node and return every path found.

    Args:
        start_label: Node label to start from, e.g. `"Equipment"`.
        start_name: The readable name of that node, e.g. `"PLT-U/FIL-207"`.
        max_hops: How deep to go. Four and five are the interesting depths —
            equipment → component → spare part → other components → other
            plants is four, and it is the question the supply-chain layer exists
            to answer.
        only_label: Keep only paths ending at this label. The traversal still
            walks through everything; this filters what comes back.

    Raises:
        TooDeep: Past `MAX_HOPS`, where a path stops explaining anything.
    """
    if max_hops > MAX_HOPS:
        raise TooDeep(f"{max_hops} hops exceeds the readable limit of {MAX_HOPS}")

    bq = client or bigquery.Client(project=config.project())
    job = bq.query(
        _sql(),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_label", "STRING", start_label),
                bigquery.ScalarQueryParameter("start_name", "STRING", start_name),
                bigquery.ScalarQueryParameter("max_hops", "INT64", max_hops),
                bigquery.ScalarQueryParameter("only_label", "STRING", only_label),
            ]
        ),
    )
    hasil = [
        Path(
            target_id=r.target_id,
            target_label=r.target_label,
            target_name=r.target_name,
            hops=int(r.hops),
            edge_labels=tuple(r.edge_labels or ()),
            node_names=tuple(r.node_names or ()),
        )
        for r in job.result()
    ]
    logger.info("traversed %s %r: %d paths", start_label, start_name, len(hasil))
    return hasil
