# Session Handover — 11 August 2026

Read `CLAUDE.md` first for the locked decisions and the accumulated traps. This
file is only what is **left to do**, and what a fresh session would otherwise
rediscover the hard way.

## Where things stand

- Branch `feat/rantai-pelaporan`, working tree clean.
- **441 tests green**, ruff clean.
- Full chain live on Cloud Run at
  `https://arka-110352541672.us-central1.run.app` (authenticated; a browser
  without a token gets 403, which looks like it is down but is not).
- All five production goals are working: BigQuery graph, GraphRAG, vector
  search, retrieval agent, question-answering agent.

```bash
python scripts/run_chain.py                       # scout → investigator → reporter
ARKA_STORE=postgres python scripts/run_chain.py   # same chain, local store
python scripts/pindai_terjadwal.py                # scheduled scan, no model calls
python scripts/migrasi_bigquery.py                # mirror all 39 tables + graph
python -m app.synthetic.generator --reset --volume-latar
python scripts/kurasi.py                          # curate candidates, no model
```

BigQuery is the default store. Both entry points refuse to run when the mirror
is stale against PostgreSQL — see `app/bigquery/kesegaran.py`.

---

## Yours, not mine

1. **Fill the placeholders** in `docs/submission.md`: name, repo link,
   `https://arka-110352541672.us-central1.run.app`, video link.
2. **Record the video.** Suggested order: scout sweeping 24 open failures and
   rejecting 22 → the escalation at margin 0.0252 → the criticality gap
   (0.30 in master data, 0.8667 computed) and the procurement conflict.
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
`app/bigquery/edges.py` (6,471 nodes, 10,094 edges, 13 labels) and
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

### Chunking, and what it did to the similarity floor

Documents were one chunk each — 54 documents, 54 chunks, `chunk_index` never
above 0. `app/retrieval/chunking.py` now splits on paragraph boundaries, falls
back to sentences, overlaps 120 characters, and fills `start_offset` /
`end_offset` against the source so a citation can be traced to its position.
Columns that existed since the first migration and had always held 0 and
`len(text)`.

The floor was then re-measured at each step, and the numbers are the point:

```
gap = weakest in-domain − strongest out-of-domain

-0.0552   four documents, one chunk each
-0.0383   chunked
-0.0007   boilerplate varied per machine type
```

The last step matters most and was self-inflicted. Every background report
opened with the *same* context and method paragraphs, so fifty near-identical
opening chunks flattened the corpus and the measurement was reading template
repetition, not retrieval. Varying them per machine type moved the bands almost
into separation.

At 0.60 the floor now admits six of seven in-domain questions and rejects all
three nonsense ones — nine of ten. ⚠️ The bands still **touch**: 0.5889
in-domain sits below 0.5896 out-of-domain. Present 0.60 as a
precision-over-recall choice, never as a boundary the data produced.

**Both improvements were to the corpus, not the model.** A similarity floor
reports the corpus it was measured on, and a bad floor is usually fixed with
better documents rather than a better number.

### Background volume — 500 equipment, 3,000 work orders

```bash
python -m app.synthetic.generator --reset --volume-latar
python scripts/kurasi.py                          # curate candidates, no model
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
Memeriksa 24 kegagalan terbuka.
  PLT-U/FIL-207 — escalate     PLT-G/FIL-412 — report
  22 diabaikan karena bukti di bawah ambang.
```

Two of twenty-four is a far better demonstration of the filter than two of three.

**Background failures carry recorded symptoms** — every open case does, down
from 17 of 20 with none. Without them, "22 ignored" meant 22 empty records, and
a filter that rejects blanks proves nothing about weighing evidence.

⚠️ They carry **no verified cause**, and that is measured rather than lazy. The
first attempt gave them causes; the background fleet then had abundant precedent
within its own models — 100 units per model, symptoms drawn from a narrow
vocabulary — and palletiser and capper cases scored **0.61–0.79** and were
reported, drowning the golden path. The system was right; with that much
evidence it should report. The data was wrong. `find_historical_cases` excludes
closed cases nobody established a cause for, so background cases are now weighed
by the same rules and rejected for having no precedent that establishes any
explanation.

Scale, measured: 9,277 rows, 6,471 graph nodes, 10,094 edges.

### Every label the graph advertises now has rows

Before: 13 node labels declared, 11 with data; `AKTIVITAS`, `MEMAKAI`,
`DIKERJAKAN_OLEH`, and `BERMODE` had **zero** rows. A graph that advertises more
than it holds is found out on the first traversal.

`app/synthetic/aktivitas.py` fills maintenance activities, technicians, spare
part consumption, and failure-mode links. All 13 labels and all 16 edge types
now carry rows.

What this buys is not tidiness. Spare parts used to reach components **only
through `component_type`** — a string match, not a history. Consumption is now
recorded, so the supply-chain question is answered from events:

```
SP-SEAL-8801 -[MEMAKAI⁻¹]-> ACT-PRESEDEN-BARAT -[AKTIVITAS⁻¹]-> WO-PRESEDEN-BARAT
SP-SEAL-8801 -[DIPASOK_OLEH⁻¹]-> seal -[MEMILIKI_KOMPONEN⁻¹]-> PLT-B/FIL-204
             -[MEMILIKI_EQUIPMENT⁻¹]-> Lini Pengisian 1 — Pabrik Barat
             -[MEMILIKI_LINE⁻¹]-> Pabrik Barat
```

Safe because nothing in `app/detection/`, `app/agents/`, or `app/reporting/`
reads these tables — checked before writing, and `tests/test_aktivitas.py` reads
those packages and fails if any of them ever starts to.

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

### Curator is built — the fifth agent

`app/curation/scoring.py` scores a candidate fact from the evidence supporting
it: quote count, extraction confidence, the authority of the document type, and
agreement. `app/agents/curator.py` decides which of those are safe to accept
without a human. Same split as detection — the number is code's, the policy is
the agent's.

```bash
python scripts/kurasi.py              # report only, writes nothing
python scripts/kurasi.py --terapkan   # apply the safe decisions
```

Five candidates, four shapes, four different outcomes:

```
✓ KLAIM-SEAL-KUAT     0.9260  setujui   three quotes from reviewed documents
✗ KLAIM-TANPA-BUKTI   0.1500  tolak     no evidence at all
→ KLAIM-HIDUP-SEAL    0.6233  eskalasi  contradicted by KLAIM-HIDUP-TORSI
→ KLAIM-HIDUP-TORSI   0.6173  eskalasi  contradicted by KLAIM-HIDUP-SEAL
→ KLAIM-NOZEL-TIPIS   0.5817  eskalasi  between the two thresholds
```

**Two refusals are enforced in code, not in the prompt**: a contradicted claim
and a claim below the rejection threshold cannot be accepted through this path
whatever the model asks. A prompt holds only while the model complies, and the
prohibitions that matter are the ones that hold when it does not.

`--terapkan` is not the default. Curation changes the knowledge the whole system
answers from; running it by accident must change nothing.

⚠️ Curator judges **textual claims**, not catalogue mappings.
`asset_identifiers` is empty because no ingestion layer fills it.

---

## Not built

- **Ingestion.** No connector, no parser, no OCR. `asset_identifiers` is empty
  because nothing fills it, which is also why Curator judges textual claims
  rather than catalogue mappings.
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

---

## Designer / infografis (11 August, sesi terpisah)

Ditulis oleh sesi lain yang berjalan bersamaan; bagian di atas bukan tulisan
saya dan tidak saya ubah. Pekerjaan designer ada di `app/designer/`, `app/agents/
designer.py`, dan `app/agents/qa.py`.

**Belum ada satu pun yang di-commit.** Working tree memuat pekerjaan dua sesi
bercampur. Periksa `git status` sebelum menganggap sebuah perubahan milik Anda.

### Yang sudah terverifikasi di halaman nyata

Dua belas perbaikan, semuanya terlihat pada gambar sungguhan (bukan hanya uji):
penamaan besaran angka, perbandingan kekritisan ARKA lawan master data,
gerbang keyakinan berjenjang, warna struktural, penempatan kartu deterministik,
penyaringan bentuk berbasis data, dan sitasi yang tidak lagi berulang.

Gerbang mutu kini tiga tingkat, dan penolakannya ditegakkan **kode**, bukan
pertimbangan model:

| Vonis | Akibat |
|---|---|
| Karangan — teks tanpa padanan di kanvas | memblokir |
| Cacat struktur — kartu hilang atau ganda | memblokir |
| Cacat cetak — salah eja teks berwenang | dilaporkan saja |

`selesai()` menolak bila pemeriksaan halaman terakhir tidak lulus. Ini menutup
kejadian nyata: penilai pernah menyatakan halaman layak kirim padahal
pemeriksaannya sendiri melaporkan teks tak disetujui dan satu kartu hilang.

### Penggambar

```bash
IMAGE_PROVIDER=vertex uv run python scripts/render_infografis.py --persona engineer
uv run python scripts/render_infografis.py --prompt-saja        # tanpa biaya
IMAGE_PROVIDER=vertex uv run python scripts/jalankan_penerbitan.py --persona engineer
```

- `openai` (bawaan, `gpt-image-2`) — belum diuji ulang sejak kredit habis.
- `vertex` (`gemini-3-pro-image`) — terbukti terbaik: 106 teks, nol tak disetujui.
- `gemini-2.5-flash-image` **tidak terpakai**: 133 dari 152 teks rusak total.

Rasio aspek diturunkan dari `IMAGE_SIZE`, jadi kedua penyedia menggambar bentuk
yang sama. Ini penting: digambar melebar, model menggandakan dua kartu dan
menghilangkan satu; pada 2:3 tegak susunannya benar.

### Sisa pekerjaan, berurut

1. **Deploy ulang.** Cloud Run masih `arka:v2` — tertinggal dari seluruh
   pekerjaan ini *dan* dari migrasi BigQuery. Sengaja ditunda, bukan terlupa.
2. Prosa Indonesia panjang masih sering rusak digambar; kalimat panjang di kaki
   halaman paling rawan. Memperpendeknya adalah perbaikan berikutnya.
3. `donut_status` dan `gauge_rating` sudah terbuka; `kpi_target` dan
   `gauge_rating` sebagai bentuk kartu masih tertutup karena kanvas tidak
   membawa `target` maupun `scale_labels`.

### Jebakan yang sudah memakan waktu

- Uji hijau tidak membuktikan apa pun di sini. `confidence_scale()` membaca
  kosakata temuan (`sedang`) padahal kanvas menyimpan `medium`, jadi selalu
  mengembalikan `None` dan gerbangnya tidak pernah tergambar — tanpa satu uji
  pun gagal. Periksa prompt atau gambar yang benar-benar dihasilkan.
- `_mirror()` dulu membaca `os.environ`, sedangkan `.env` dimuat pydantic ke
  `Settings`. Akibatnya jejak audit diam-diam tidak tersalin ke GCS di lokal.
  Sekarang membaca `Settings` lebih dulu.
- `app/synthetic/finding_contoh.py` dan jalur BigQuery menghasilkan **angka
  berbeda untuk seal yang sama** (0,84 lawan 0,87 terhadap master data 0,30).
  Sebelum mengoreksi angka di dokumen, pastikan dulu kalimat itu merujuk data
  yang mana.
- Modul `app/designer/inspection.py` menuntut `GOOGLE_CLOUD_PROJECT`, yang baru
  terpasang ketika `app.agents` diimpor. Memakainya langsung tanpa impor itu
  akan gagal dengan pesan yang menyesatkan.
