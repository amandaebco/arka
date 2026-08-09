# Implementation Plan: Modul `designer`

**Spec**: [spec.md](spec.md) · **Constitution**: 1.2.0

Modul ini sebagian besar **dipindahkan**, bukan ditulis baru. Purwarupa di luar
repositori sudah tervalidasi dengan 108 pengujian deterministik. Rencana ini
menetapkan apa yang pindah apa adanya, apa yang berubah, dan apa yang dibuang.

## Peta pemindahan

| Asal (purwarupa) | Tujuan | Perlakuan |
|---|---|---|
| `design/` (44 aset YAML) | `app/designer/design/` | Pindah apa adanya |
| `design_kb/loader.py` | `app/designer/knowledge/loader.py` | Pindah; muat sekali saat startup |
| `design_kb/schemas.py` | `app/designer/knowledge/schemas.py` | Pindah apa adanya |
| `design_kb/validation.py` | `app/designer/knowledge/validation.py` | Pindah apa adanya |
| `models/vds_schema.py` | `app/designer/presentation.py` | Pindah; `sections` jadi masukan |
| `composer/prompt_composer.py` | `app/designer/composer.py` | Pindah; sumber isi berubah |
| `composer/prompt_renderer.py` | `app/designer/renderer.py` | Pindah apa adanya |
| `prompts/templates/*.md` | `app/designer/templates/` | Pindah apa adanya |
| `prompts/system/visual_design_agent.md` | `app/designer/prompts/` | Pindah; menu berubah |
| `services/image_service.py` | `app/designer/image.py` | Pindah; pakai `app.core.config` |
| `models/report_content.py` | — | **Dibuang** — `Finding` menggantikannya |
| `agents/structuring_agent.py` | — | **Dibuang** — `Finding` sudah terstruktur |
| `services/report_parser.py` | — | **Dibuang** — tidak ada markdown untuk diurai |
| `agents/qa_agent.py` | `app/agents/penilai.py` | **Dilebur** ke penilai yang sudah ada |
| `agents/vds_refinement_agent.py` | `app/agents/designer.py` | Dilebur jadi putaran kedua designer |
| `pipeline/orchestrator.py` | — | **Dibuang** — ADK yang mengorkestrasi |
| `tests/*` | `tests/designer/` | Pindah; yang menguji parser dibuang |

Tiga modul dibuang karena `Finding` menggantikan seluruh perannya. Ini penyederhanaan
terbesar dari pemindahan: satu panggilan model hilang, dan bersamanya hilang pula
seluruh kelas kesalahan ekstraksi.

## Yang berubah, bukan sekadar pindah

**Sumber isi.** Composer sebelumnya membaca `ReportContent` hasil ekstraksi. Sekarang
membaca `Finding` langsung. Pemetaannya lurus karena keduanya sama-sama terstruktur:

| Blok ARKA | Sumber di `Finding` |
|---|---|
| `ringkasan` | `gejala`, `keyakinan` |
| `kandidat_penyebab` | `kandidat_terurut`, `skor` |
| `preseden_lintas_pabrik` | `preseden` |
| `rantai_kausal` | `rantai_kausal` |
| `sparepart_kritis` | `sparepart`, `selisih` |
| `rekomendasi` | `rekomendasi`, `prioritas` |
| `jejak_penalaran` | `jejak_penalaran` |
| `sitasi` | `semua_sitasi()` |

**Ketersediaan data.** Purwarupa memakai `derive_data_keys()` atas `ReportContent`.
Di sini diturunkan dari field `Finding` yang terisi, dan disatukan dengan
`Blok.tersedia` yang sudah ada di `app/reporting/blocks.py`. Satu mekanisme, bukan dua.

**Pemilihan blok.** Bukan lagi keputusan designer. `reporter` menetapkannya; designer
menerimanya lewat state.

**Keyakinan.** `Keyakinan` di `Finding` sudah tiga tingkat (`tinggi|sedang|rendah`),
sama persis dengan skema token di pustaka desain. Pemetaannya langsung.

## Bentuk ADK

```
LoopAgent(max_iterations=3)
  ├── designer_agent   LlmAgent  — usulkan penekanan dan bentuk visual
  └── penilai_agent    LlmAgent  — rubrik infografis, sudah ada untuk memo
```

Mengikuti pola `app/agents/qa.py` yang sudah berjalan untuk `reporter ↔ penilai`.

**Kunci state:**

| Kunci | Penulis | Pembaca |
|---|---|---|
| `finding` | investigator | reporter, designer |
| `blok_terpilih` | reporter | designer |
| `spesifikasi_penyajian` | designer | tool penggambar |
| `masukan_penilai_visual` | penilai | designer |

**Tool deterministik** yang dipanggil designer, bukan dikerjakan model:
`susun_spesifikasi` (validasi usulan terhadap pustaka), `gambar_halaman`
(kompilasi prompt + panggil penyedia gambar), `terbitkan_artifact`.

**Catatan utang.** `LoopAgent` sudah usang di ADK 2.x. Diikuti karena penilai yang
ada memakainya; migrasi ke `google.adk.workflow` dikerjakan bersama, bukan sendiri.

## Urutan kerja

1. Pindahkan pustaka desain dan pemuatnya; pastikan validasi lolos di repo ini.
2. Ganti sumber isi composer dari `ReportContent` ke `Finding`.
3. Bungkus designer sebagai `LlmAgent` dengan tool deterministik.
4. Perluas `penilai` dengan rubrik infografis.
5. Rangkai `LoopAgent`, terbitkan sebagai ADK Artifact.
6. Pindahkan pengujian; buang yang menguji parser.

Langkah 1 dan 2 memikul sebagian besar nilai. Bila waktu menipis, langkah 4 boleh
diringkas menjadi pemeriksaan deterministik saja — imbangan Prinsip I tetap utuh
karena FR-012 adalah pemeriksaan kode, bukan pertimbangan model.
