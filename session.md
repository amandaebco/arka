# Session Handover — 11 August 2026

Read `CLAUDE.md` first for the locked decisions and the accumulated traps. This
file is only what is **left to do**, and what a fresh session would otherwise
rediscover the hard way.

## Where things stand

- Branch `feat/rantai-pelaporan`, 33 commits, working tree clean.
- **262 tests green**, ruff clean on everything except four pre-existing
  long-line warnings in demo scripts.
- Full chain live on Cloud Run at
  `https://arka-110352541672.us-central1.run.app` (authenticated; a browser
  without a token gets 403, which looks like it is down but is not).
- All five production goals are working: BigQuery graph, GraphRAG, vector
  search, retrieval agent, question-answering agent.

```bash
python scripts/run_chain.py                        # scout → investigator → reporter
ARKA_STORE=bigquery python scripts/run_chain.py    # same chain, BigQuery
python scripts/pindai_terjadwal.py                 # scheduled scan, no model calls
python scripts/uji_bigquery_graph.py               # sync PostgreSQL → BigQuery
python -m app.synthetic.generator --reset          # reseed the golden path
```

---

## Yours, not mine

1. **Fill the placeholders** in `docs/submission.md`: name, repo link,
   `https://arka-110352541672.us-central1.run.app`, video link.
2. **Record the video.** Suggested order: scout scanning three failures and
   ignoring one → the escalation → the criticality gap and the procurement
   conflict.
3. **Merge the branch** when ready: `git merge --ff-only feat/rantai-pelaporan`.

---

## BigQuery is now the full mirror (11 August, later)

All **39 canonical tables** are in `ebco-aihack-amanda.arka`, verified row by row
on both sides. Defects 1 and 3 below are closed by this; defect 2 stands until
the generator writes to BigQuery directly.

```bash
python scripts/migrasi_bigquery.py            # mirror all 39 tables + graph
python scripts/migrasi_bigquery.py --verify   # row counts, both sides
python scripts/migrasi_bigquery.py --index    # re-embed document chunks
```

`app/detection/bigquery_repository.py` now reads canonical tables, so parity is
exact and `symptom_names` carries sentences: `0.9071` / `0.8819`, margin
`0.0252`, 5 precedents, 8 citations, `SP-SEAL-8801` at `0.8667` — identical from
both stores.

### `GRAPH_EXPAND` is not a traversal function — measured, not assumed

Three limits, each found by hitting it:

1. more than **10 node tables** is refused;
2. the graph must funnel into a **single sink**;
3. **convergent paths are rejected** — *"the subgraph reachable from start node
   'failure_events' contains a convergent path involving node 'equipment'"*.

Equipment is reachable directly and through its components, so this graph
converges by construction. No trimming fixes that. `GRAPH_EXPAND` is a snowflake
denormaliser for one fact table, and full GQL `MATCH` still wants Enterprise.

**The graph is therefore an edge list walked by a recursive CTE** —
`app/bigquery/edges.py` (70 nodes, 111 edges, 13 labels) and
`app/bigquery/traversal.py`. Depth is a parameter, cycles are guarded with
`STRPOS` over a delimited trace (BigQuery's recursive term rejects subqueries),
and the full path comes back as data.

Edges are walked **both ways**, reversed steps marked `⁻¹`. Forward-only every
route dead-ends at a spare part after three hops; the reverse step is what makes
four and five reachable, and it is the direction the supply-chain question runs:

```
PLT-U/FIL-207 -[MEMILIKI_KOMPONEN]-> seal -[DIPASOK_OLEH]-> SP-SEAL-8801
              -[DIPASOK_OLEH⁻¹]-> seal -[MEMILIKI_KOMPONEN⁻¹]-> PLT-G/FIL-412
```

**Multi-hop traversal can now be claimed in the pitch** — with the path printed,
which is the part that makes it checkable rather than merely asserted.

### BigQuery is the default store

`ARKA_STORE` unset now means **bigquery**. A *misspelt* value still falls back to
PostgreSQL — reaching for the cloud should take spelling it right, and a wrong
answer from the wrong store looks exactly like a right one.

`tests/conftest.py` pins the suite to PostgreSQL. Without it the agent tests
went over the network: `test_scout_agent.py` setup jumped to 47s each and the
full suite from 12s to 261s. Speed is the symptom; the reason is that PostgreSQL
is where the generator writes, so a test against BigQuery tests the last sync
rather than the code. ⚠️ **The BigQuery path is therefore not covered by the
suite** — the hand-run parity check is what guards it.

### Citations are filtered per candidate now

`group_by_cause` used to attach **every** document to **every** candidate.
Invisible at four documents; at 54 it would have put fifty mixer reports in a
memo about filling heads. Documents now attach on a **two-term overlap** with
the cause name. One term was measured to be too loose — a mixer report matched
"degradasi seal … akibat batch material" through the single word `batch`.

Golden path citations unchanged at 8.

### Embedding model is `gemini-embedding-2`

Also 3072 dimensions, so the schema did not change — and that is the trap, not
the reassurance. Vectors from two models are not comparable; the index was fully
rebuilt. ⚠️ **`gemini-embedding-2` ignores batching**: handed three texts it
returns one vector, with no error. `app/retrieval/embedding.py` now sends one
text per request and checks the count.

### The similarity threshold does not separate — measured, not suspected

Corpus raised to **54 documents** (`app/synthetic/dokumen_latar.py`) precisely so
`MIN_SIMILARITY` could be measured on something. The result is the useful kind
of negative:

```
in-domain   0.7703  0.7542  0.7239  0.6512  0.6359  0.5140 ←
out-domain  0.5692 ←  0.5307  0.5018
```

The bands **overlap**. The weakest in-domain question scored 0.5140 while
retrieving the *correct* document, below the strongest nonsense question at
0.5692. **No single threshold separates them.** On four documents the gap looked
clean; that was the corpus, not the system.

0.60 is kept as a **precision-over-recall** choice — silence rather than a
confident wrong citation — and should be described that way in the pitch, not as
a calibrated boundary. The real fix is a relative test (margin between top hit
and the rest, or a rerank), because "best match" and "good match" are different
questions.

### Background volume — 500 equipment, 3,000 work orders

```bash
python -m app.synthetic.generator --reset --volume-latar
```

Optional, not the default: tests run on the golden path and should not pay for
thousands of rows. `app/synthetic/volume_latar.py`.

**The golden path is isolated by construction, not by inspection.** Three leak
paths exist and all three are closed by disjoint sets, guarded in
`tests/test_volume_latar.py`:

| Leak | Closed by |
|---|---|
| `find_historical_cases` filters `equipment_model` | background models ≠ `MODEL_FILLER` |
| `find_spare_parts` reaches plants via `component_type` | background types ∩ `KOMPONEN_FILLER` = ∅ |
| `find_next_maintenance` filters `equipment_tag` | background work orders only on background units |

Verified after seeding: `0.9071` / `0.8819`, margin `0.0252`, `SP-SEAL-8801` at
`0.8667` — every figure unmoved, from both stores.

What *does* change, deliberately, is the scan. Open failures are not filtered by
model — Scout must sweep the whole fleet — so background failures do surface and
are rejected on evidence:

```
Memeriksa 20 kegagalan terbuka.
  PLT-U/FIL-207 — escalate     PLT-G/FIL-412 — report
  18 diabaikan karena bukti di bawah ambang.
```

Two of twenty is a far better demonstration of the filter than two of three.

Scale, measured: 4,689 rows, 4,630 graph nodes, 4,671 edges. Traversal from one
equipment returns 1,086 paths at four hops and 1,580 at five, in seconds.

---

## Known defects — real, not cosmetic

### 1. ~~Symptoms render as codes when reading from BigQuery~~ — fixed

Closed by the full mirror: `symptoms` is a real table on both sides now.

### 2. The BigQuery data is a copy

It is synced from PostgreSQL. Change the golden path without re-running the
sync and BigQuery answers from stale data **without any error** — the same
failure mode that led us to query canonical tables rather than the AGE
projection. This is the **last** thing standing between here and BigQuery as the
sole source: `app/synthetic/generator.py` still writes to PostgreSQL only.

### 3. ~~The graph is one hop~~ — fixed

13 labels, 111 edges, traversed to five hops. See above.

### 4. The similarity floor is tuned to four documents

`MIN_SIMILARITY = 0.60` in `app/retrieval/vector_store.py`. Measured, not
guessed: in-domain paraphrases scored 0.61–0.72, an out-of-domain question still
reached 0.56. This is a property of a four-document corpus and **must be
re-measured** as the estate grows.

---

## Not built

- **Curator** — the fifth agent. Approval of mappings is entirely manual. The
  cut order in `CLAUDE.md` allows it to become a batch script.
- **Traversal is not wired into any agent.** `app/bigquery/traversal.py` works
  and is tested, but the detection chain still answers its four questions with
  joins, and parity depends on that. Connecting it to the spare-part impact
  radius is the obvious next step and touches figures that reach the memo, so it
  needs a parity re-run, not just a green test suite.
- **Agent Engine with our own image.** `image_spec` builds and the resource comes
  up, but exposes no query surface: `class_methods` is empty, `agent_framework`
  is `custom`, and both `:query` and `:streamQuery` return 404 because our
  container serves `adk api_server` while that runtime expects its own HTTP
  contract. Next thing to try: `agent_server_mode`. The pickle path works and is
  recorded in `scripts/deploy_hello.py`.
- **Language migration.** `app/reporting/`, `app/synthetic/`, `app/designer/`,
  and their tests are still Indonesian. The rule is one module at a time,
  complete, including its tests — a half-translated file is worse than an
  untouched one.

---

## Left alone deliberately

**22 objects in `gs://ebco-aihack-amanda-arka-staging/dashboards/` contain client
data** — refinery unit, location, equipment tags — from dashboard testing with
the CMRP prompt. The repository, git history, PostgreSQL, and BigQuery are all
verified clean; this is the one place that is not. Amanda chose to leave them on
11 August. They are only reachable through a signed URL, and they can be
regenerated from fictional data at any time.

`python scripts/uji_bigquery_graph.py --hapus` removes the BigQuery dataset when
it is no longer needed. Keeping it costs a few kilobytes and proves the
production path on demand.

---

## Traps that already cost hours

- `gcloud run deploy` crashes under its bundled Python 3.9. Prefix every gcloud
  command with `CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.12`.
- Building on Apple silicon for Cloud Run needs `--platform linux/amd64`.
  `gcloud builds submit` is denied despite `roles/editor`; `docker buildx` and a
  direct push work.
- **Dependencies that are only transitively present pass locally and fail on
  deploy.** `google-cloud-bigquery` arrived through `aiplatform`, lived in the
  virtualenv, and was absent from the image. Anything imported must be declared
  in `pyproject.toml`.
- `ML.GENERATE_EMBEDDING` needs a connection whose service account must be
  granted Vertex access, and this account cannot `setIamPolicy`. Embeddings are
  therefore produced outside BigQuery; `VECTOR_SEARCH` needs no connection.
- BigQuery rejects correlated subqueries across tables. Write them as aggregate
  joins.
- **`kasus-sepele-selatan` in `app/synthetic/jalur_emas.py` exists to be
  ignored.** Do not tidy it away: without a case that fails the bar, the scout's
  filter cannot be questioned, and `test_something_is_actually_ignored` turns
  red.
- The escalation margin (0.0252) was reached by seeding a third torque
  precedent. Weights and thresholds are published policy and were never touched.
  If the demo stops escalating, look at the data, not the formula.
