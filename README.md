# ARKA — Asset Reliability Knowledge Agent

> Autonomous multi-agent system revealing root causes of industrial equipment failures with end-to-end evidence traceability.

**EBCO AI Hackathon 2026 · Category B — AI Agent · Theme: Knowledge Management Solution**

---

## Status

✅ **Ready for Submission & Evaluation — EBCO AI Hackathon 2026.**

## Summary

ARKA investigates root causes of machine failures across multi-plant manufacturing environments. Operating over a GraphRAG Knowledge Graph (39 canonical BigQuery tables, graph nodes & edges, and vector search), ARKA traces hidden connections across assets, maintenance work orders, maintenance history, inspection reports, and supplier sparepart batches — all of it fully synthetic. It synthesizes findings into publication-ready executive deliverables (PDF Memos, Official Memos, Slide Decks, and Visual Infographics) where every claim is fully traceable to original evidence.

## Architecture

```
        ┌────────────────────────────────────────────────────────┐
        │                     Google ADK                         │
        │    Scout → Investigator → Reporter → Designer          │
        │    QA Evaluator + Vision Inspector (Quality Gate)      │
        │    Curator (Knowledge Graph Policy Enforcer)           │
        │    Interactive Q&A (Conversational GraphRAG)          │
        └───────────────────────────┬────────────────────────────┘
                                    │
        ┌───────────────────────────┴────────────────────────────┐
        │   BigQuery — 39 Canonical Tables (Primary Store)        │
        │   graph_nodes / graph_edges · VECTOR_SEARCH            │
        │   (Optional local fallback: PostgreSQL + Apache AGE)   │
        └───────────────────────────┬────────────────────────────┘
                                    │
        ┌───────────────────────────┴────────────────────────────┐
        │  ADK Deliverables: Executive Memo · Infographic · Deck │
        └────────────────────────────────────────────────────────┘
```

## Specialized AI Agents

ARKA orchestrates **7 specialized AI agents** built on **Google ADK** with strict isolation of concerns:

### 1. Scout Agent (`adk_agents/scout` / `app/agents/scout.py`)
- **Role**: Autonomous fleet-wide failure scanner.
- **Function**: Continuously scans open machine failures across multi-plant fleets, calculates similarity against historical resolved cases, and selects non-trivial cases that warrant deep investigation.
- **Key Tools**: `scan_fleet`, `explain_skip`.
- **Output**: Shortlisted failure candidates with clear rationale for skipped cases.

### 2. Investigator Agent (`adk_agents/investigator` / `app/agents/investigator.py`)
- **Role**: Multi-hop GraphRAG root cause investigator.
- **Function**: Performs 4–5 hop graph traversal across `Asset -> WorkOrder -> Notification -> SparePart -> Plant`. Collects evidence from inspection reports, technician notes, FMEA, and supplier batch numbers to pinpoint root causes.
- **Key Tools**: `list_open_cases`, `investigate_case`.
- **Output**: Structured `Finding` model containing verified causes, cross-plant precedents, and sparepart criticality.

### 3. Reporter Agent (`adk_agents/reporter` / `app/agents/reporter.py`)
- **Role**: Executive document synthesizer & layout composer.
- **Function**: Selects document format (`memo`, `nota_dinas`, `laporan`, `dashboard`), orders information blocks, and writes introductory narrative explaining significance.
- **Hard Boundaries**: **Never mentions numbers in narrative** (rendered via tables only) and **never uses em-dashes ("—")**.
- **Key Tools**: `muat_temuan`, `ringkas_temuan`, `terbitkan_dokumen`.
- **Output**: Single-page PDF Memo, Official Letter (`Nota Dinas`), Full Report, or Interactive Dark Glassmorphism Web Dashboard.

### 4. Designer Agent (`adk_agents/designer` / `app/agents/designer.py`)
- **Role**: Visual presentation & canvas layout engine.
- **Function**: Determines dominant block emphasis and assigns visual card shapes (from 17 data-driven form patterns). Renders 1-page visual poster infographics using Playwright.
- **Key Tools**: `ringkas_penyajian`, `terbitkan_infografis`.
- **Output**: High-definition HD Poster Infographic (`1024x1536` canvas).

### 5. QA Agent & Visual Inspector (`app/agents/qa.py` & `app/designer/inspection.py`)
- **Role**: Vision-based anti-hallucination quality gate.
- **Function**: Transcribes rendered infographic images using **Gemini Vision AI (OCR)** and compares rendered text against authoritative `Finding` data using fuzzy matching.
- **Quality Enforcement**: Blocks publication on **Inventions/Hallucinations** (unauthorized text ≥ 12 chars) and logs **Misprints** for audit.
- **Output**: Quality verdict (`APPROVED` / `REJECTED_WITH_FEEDBACK`) with audit logs.

### 6. Curator Agent (`app/agents/curator.py`)
- **Role**: Knowledge Graph ingestion policy enforcer.
- **Function**: Evaluates newly extracted candidate facts from inspection documents. Auto-accepts facts backed by multiple non-contradictory sources, rejects unevidenced claims, and escalates ambiguous facts to human engineers.
- **Key Tools**: `daftar_kandidat`, `putuskan_kandidat`, `ringkas_kurasi`.
- **Output**: Approved graph updates and human escalation queue.

### 7. Interactive Q&A Agent (`adk_agents/tanya_jawab` / `app/agents/tanya_jawab.py`)
- **Role**: Conversational GraphRAG assistant.
- **Function**: Serves real-time natural language queries from reliability engineers regarding equipment history, failure causes, and graph relationships.
- **Key Tools**: `cari_konteks`, `telusuri_graph`.
- **Output**: Citation-backed technical answers referencing exact graph paths and source document chunks.

## Running & Evaluation

### 🚀 One-Command Bootstrap (Recommended)
For seamless evaluator onboarding, execute the automated bootstrap script:

```bash
bash scripts/bootstrap.sh
```
This script automatically validates prerequisites, configures `.env`, launches containerized PostgreSQL (Apache AGE + pgvector), executes database migrations, and seeds synthetic datasets in one command.

### Manual Setup
```bash
cp .env.example .env                       # Credentials setup
uv sync                                    # Dependencies
docker compose up -d                       # PostgreSQL container
uv run alembic upgrade head                # Schema migration

uv run python -m app.synthetic.generator --reset --volume-latar
uv run python scripts/migrasi_bigquery.py --full    # Copy -> Verify -> Index

uv run python scripts/run_chain.py         # Run Investigator -> Reporter (headless)
# The full Scout -> Investigator -> Reporter chain is served as one agent:
#   uv run adk api_server adk_agents      # then call the `arka` agent
uv run python scripts/pindai_terjadwal.py  # Scheduled scan
```

> **Database Architecture Note:**
> The primary data store and production architecture of ARKA is **100% Native Cloud BigQuery** on GCP — encompassing 39 canonical tables, Knowledge Graph (`graph_nodes` & `graph_edges`), and `VECTOR_SEARCH`. Powered by **Direct BigQuery Ingestion (Spec 007)**, data is ingested directly into BigQuery without intermediate databases. Local PostgreSQL (Apache AGE) serves strictly as an *optional offline dev fallback* for offline testing without GCP connectivity.

## Key Features & Submission Checklist

1. **GraphRAG & BigQuery Knowledge Graph**: Unifies 39 canonical BigQuery tables with `graph_nodes` and `graph_edges` for hybrid relational + graph queries.
2. **VectorDB Retrieval**: Combines `pgvector` and BigQuery `VECTOR_SEARCH` for high-performance semantic chunk retrieval.
3. **Synthetic Document Corpus**: Generates **50 structured technical inspection documents** (`app/synthetic/dokumen_latar.py`).
4. **Multi-Hop Graph Traversal**: Executes **4 to 5 hop** deep graph walks (`Asset -> WorkOrder -> Notification -> SparePart -> Plant`).
5. **Comprehensive Use Case Coverage**:
   - **Reliability Case**: Equipment root cause analysis, maintenance history, FMEA, and technician notes.
   - **Supply Chain Case**: Distributed sparepart batch tracking (`specs/006-batch-sparepart-tracking`) to detect vendor batch defects across plants.
6. **Multi-Tier Caching Layer**: Centralized TTL-based caching (`app/core/cache.py`) optimizing database queries and reducing LLM token consumption.

## Infographics & Audit Trail

The Designer Agent publishes single-page infographics from findings completed by the Reporter. All canvas text is constructed verbatim from `Finding` data.

Persona options: `engineer` (technical diagnosis) and `reliability_manager` (default executive summary).

```bash
uv run python scripts/render_infografis.py --persona engineer   # Render single page
uv run python scripts/render_infografis.py --prompt-saja        # Inspect prompt cost-free
uv run python scripts/jalankan_penerbitan.py                    # Full chain execution
uv run python scripts/jalankan_penerbitan.py --hanya-designer   # Skip Reporter
```

**Audit Trail**: Every publication run saves a complete audit trail in `out/infografis/<timestamp>-<finding>/`, containing findings, canvas content, specifications, prompts, rendered pages, and inspection verdicts. If `ARTIFACT_GCS_BUCKET` is configured, artifacts are mirrored to Google Cloud Storage.

## Synthetic Data

**All data is 100% synthetically generated.** No real-world proprietary data is used.

## Future Roadmap & Enterprise Expansion

1. **IoT / SCADA Telemetry Streaming (Real-time Prescriptive Alert)**: Connect ARKA to Pub/Sub IoT telemetry streams to trigger proactive agent scans before machine breakdown occurs.
2. **Multi-Modal Technical Drawing Parsing**: Leverage Gemini Vision to parse P&ID diagrams, CAD schematics, and thermal imaging directly into knowledge graph edges.
3. **Human-in-the-Loop (HITL) Active Learning**: Interactive UI for chief reliability engineers to approve/correct agent findings, writing verified labels back to the graph (`VERIFIED_BY_ENGINEER`).
4. **Direct Connectors for SAP PM & IBM Maximo**: Zero-ETL connectors mapping native ERP/CMMS schemas into ARKA's 39 canonical tables.
5. **Closed-Loop Action Execution**: Automated drafting of SAP Work Orders or sparepart batch reservations upon report approval.

## Development & Spec Kit

Built using **Spec-Driven Development** ([GitHub Spec Kit](https://github.com/github/spec-kit)).
Specifications are located in `.specify/` and `specs/` (`specs/001` through `specs/008`).

```bash
uv run pytest
uv run ruff check .
```
