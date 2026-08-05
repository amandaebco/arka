# ARKA — Asset Reliability Knowledge Agent

> Agent otonom yang menyingkap akar masalah keandalan mesin, dengan bukti yang bisa ditelusuri.

**EBCO AI Hackathon 2026 · Kategori B — AI Agent · Tema: Knowledge Management Solution**

---

## Status

🚧 Dalam pengembangan. Dokumen submission lengkap menyusul.

## Ringkasan

ARKA menyelidiki akar masalah kegagalan mesin di manufaktur multi-pabrik. Berjalan di atas
knowledge graph, ia menelusuri hubungan antara aset, riwayat perbaikan, dokumen inspeksi, dan
rantai pasok sparepart — untuk menemukan penyebab yang tidak terlihat di sistem manapun, lalu
menyusunnya menjadi dokumen yang setiap klaimnya bisa ditelusuri ke sumber aslinya.

## Arsitektur

```
        ┌──────────────────────────────────────────────┐
        │              Google ADK                      │
        │  Scout → Investigator → Reporter             │
        │  Curator (ortogonal)                         │
        └───────────────────┬──────────────────────────┘
                            │
        ┌───────────────────┴──────────────────────────┐
        │   PostgreSQL 16 + Apache AGE + pgvector      │
        │   public (kanonik) → arka_kg (graph)         │
        └───────────────────┬──────────────────────────┘
                            │
        ┌───────────────────┴──────────────────────────┐
        │  ADK Artifacts: memo · infografis · deck     │
        └──────────────────────────────────────────────┘
```

## Menjalankan

```bash
cp .env.example .env          # isi kredensial
docker compose up -d          # PostgreSQL + AGE + pgvector
uv sync                       # dependensi
alembic upgrade head          # skema
python -m app.synthetic.generator --scale 1x
python -m app.graph.project   # proyeksi graph
uvicorn app.main:app --reload
```

## Data

**Seluruh data dibangkitkan secara sintetis.** Tidak ada data nyata milik pihak manapun.

## Pengembangan

Proyek ini memakai **Spec-Driven Development** ([GitHub Spec Kit](https://github.com/github/spec-kit)).
Spesifikasi ada di `.specify/`; alurnya `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

```bash
pytest
ruff check .
```
