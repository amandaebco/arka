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

## Known defects — real, not cosmetic

### 1. Symptoms render as codes when reading from BigQuery

`app/detection/bigquery_repository.py` fills `symptom_names` with codes
(`GJL-BOCOR-KEPALA`) because the `symptoms` table was never synced. A document
published from the BigQuery path therefore prints codes where the PostgreSQL
path prints sentences. Fix: add `symptoms` and `causes` to the sync in
`scripts/uji_bigquery_graph.py` and join the display name. ~20 minutes.

### 2. The BigQuery data is a copy

It is synced from PostgreSQL. Change the golden path without re-running the
sync and BigQuery answers from stale data **without any error** — the same
failure mode that led us to query canonical tables rather than the AGE
projection. In production this disappears, because BigQuery becomes the source.

### 3. The graph is one hop

The property graph has two node labels and one edge:
`Equipment --TERJADI_PADA--> FailureEvent`. Everything else — symptoms, causes,
components, spare parts — is a SQL join around it.

**Do not claim multi-hop traversal in the pitch.** What is true and strong:
cross-plant precedent discovery over a knowledge graph, with a traversal order
that is fixed and auditable.

Making it genuinely multi-hop means adding node labels for Symptom, Cause,
Component, SparePart, Plant and edges between them. ~30–45 minutes; the DDL
pattern is in `scripts/uji_bigquery_graph.py`. Worth it for EBCO — it is what
lets one traversal answer "what else uses this material batch".

### 4. The similarity floor is tuned to four documents

`MIN_SIMILARITY = 0.60` in `app/retrieval/vector_store.py`. Measured, not
guessed: in-domain paraphrases scored 0.61–0.72, an out-of-domain question still
reached 0.56. This is a property of a four-document corpus and **must be
re-measured** as the estate grows.

---

## Not built

- **Curator** — the fifth agent. Approval of mappings is entirely manual. The
  cut order in `CLAUDE.md` allows it to become a batch script.
- **Background volume** — ~5,000 equipment, ~20,000 work orders over the golden
  path. Everything currently runs on 130 rows, so nothing has been tested at
  any scale.
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
