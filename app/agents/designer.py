"""Agent `designer` — decides how the selected blocks are presented visually.

Incoming handover is the block list `reporter` already settled on, held in state.
This module never revisits that choice: two modules holding the same decision is
exactly what Principle V forbids. What it decides is narrower and its own —
which block dominates the page, and what visual form each one takes.

The boundary this module guards: the model proposes identifiers, code produces
every string. `content.py` fixes the text from the finding, `composer.py` compiles
it, and the drawing provider only ever receives values that were already final.
That is what keeps the infographic inside the exception granted by Constitution
1.2.0 rather than outside Principle I.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.agents.reporter import KUNCI_TEMUAN
from app.core.config import get_settings
from app.designer.composer import compose_prompt
from app.designer.content import build_content
from app.designer.image import DrawingUnavailable, draw_page
from app.designer.knowledge import DesignKnowledgeBase, DesignKnowledgeBaseError
from app.designer.presentation import PresentationSpec, normalise, validate
from app.designer.trail import RunTrail
from app.reporting.blocks import URUTAN_BAKU, susun_blok
from app.reporting.finding import Finding

logger = logging.getLogger(__name__)

# Handover keys. `selected_blocks` is written by reporter; the rest belong here.
KUNCI_BLOK = "urutan_terakhir"
KUNCI_SPESIFIKASI = "spesifikasi_penyajian"
KUNCI_MASUKAN_VISUAL = "masukan_penilai_visual"
# Nama berkas artifact terakhir, supaya penilai dapat membuka gambarnya.
KUNCI_BERKAS_INFOGRAFIS = "berkas_infografis"
# Folder jejak audit run terakhir, supaya hasilnya dapat ditelusuri di luar sesi.
KUNCI_JEJAK = "jejak_infografis"

# Reader profiles carried over from the design library. One is chosen per run;
# the library holds more, but only these two have been exercised against ARKA data.
PERSONA = {
    "engineer": "engineer_diagnosis",
    "reliability_manager": "reliability_strategy",
}
DEFAULT_PERSONA = "reliability_manager"

_kb: DesignKnowledgeBase | None = None


def knowledge_base() -> DesignKnowledgeBase:
    """Load the design library once per process, failing loudly if inconsistent."""
    global _kb
    if _kb is None:
        _kb = DesignKnowledgeBase.load()
    return _kb


def _read_finding(tool_context: ToolContext) -> Finding | None:
    mentah = tool_context.state.get(KUNCI_TEMUAN)
    if not mentah:
        return None
    if isinstance(mentah, Finding):
        return mentah
    try:
        return Finding.model_validate(
            json.loads(mentah) if isinstance(mentah, str) else mentah
        )
    except Exception as exc:  # noqa: BLE001 — reported to the model, not raised
        logger.warning("Temuan di state tidak dapat dibaca: %s", exc)
        return None


def _selected_blocks(finding: Finding, tool_context: ToolContext) -> list:
    """Blocks the reporter settled on, filtered to those that actually have data."""
    semua = susun_blok(finding)
    order = tool_context.state.get(KUNCI_BLOK) or list(URUTAN_BAKU)
    return [semua[b] for b in order if b in semua and semua[b].tersedia]


def ringkas_penyajian(persona: str, tool_context: ToolContext) -> str:
    """Describes what may be presented and which visual forms are available.

    Call this before proposing a presentation. It reports the blocks the reporter
    selected, how much content each holds, and the visual forms the chosen style
    permits — so the proposal is grounded rather than guessed.

    Args:
        persona: "engineer" or "reliability_manager". Anything else falls back to
            the default reader profile.
        tool_context: Injected by ADK.

    Returns:
        The blocks available, their content shape, and the permitted visual forms.
    """
    finding = _read_finding(tool_context)
    if finding is None:
        return "Belum ada temuan di sesi ini. Muat temuan lebih dulu."

    try:
        kb = knowledge_base()
    except DesignKnowledgeBaseError as exc:
        return f"Pustaka desain tidak konsisten dan tidak dapat dipakai: {exc}"

    style = PERSONA.get(persona, PERSONA[DEFAULT_PERSONA])
    blok = _selected_blocks(finding, tool_context)
    isi = build_content(blok)
    tersedia = kb.resolve_style(style)

    baris = [
        f"Style: {style} — untuk {tersedia['audiences'][0]['name']}.",
        f"Kapasitas halaman: {kb.page_capacity(style)} kartu.",
        f"Bahasa kanvas: {isi.keyakinan and 'id' or 'id'}.",
        "",
        "Blok yang dipilih reporter dan jumlah butirnya:",
    ]
    for satu in blok:
        jumlah = len(isi.items(satu.id))
        catatan = f"{jumlah} butir" if jumlah else "tanpa isi — tidak akan dirender"
        baris.append(f"  - {satu.id} ({satu.judul}): {catatan}")

    baris += [
        "",
        "Bentuk visual yang allowed style ini:",
        "  " + ", ".join(p["id"] for p in tersedia["visualization_patterns"]),
        "",
        f"Tingkat keyakinan temuan: {finding.keyakinan}. "
        f"Eskalasi: {'ya' if finding.perlu_eskalasi else 'tidak'}.",
        "Kamu tidak boleh menambah atau membuang blok — hanya menimbang dan memilih bentuk visual.",
    ]
    return "\n".join(baris)


async def terbitkan_infografis(
    persona: str,
    penekanan_json: str,
    bentuk_json: str,
    aksen_json: str,
    rationale: str,
    tool_context: ToolContext,
) -> str:
    """Compiles the presentation, draws the page, and saves it as a session artifact.

    Args:
        persona: "engineer" or "reliability_manager".
        penekanan_json: JSON map {block_id: "dominant"|"primary"|"secondary"|
            "tertiary"}. At most one block may be dominant.
        bentuk_json: JSON map {block_id: visual_form_id}. Only forms the style
            permits. Omit a block to render it as plain text, which is always safe.
        aksen_json: JSON map {value: severity_key} for status values that should
            carry a semantic colour.
        rationale: One sentence on the main presentation decision and why this
            finding called for it.
        tool_context: Injected by ADK.

    Returns:
        The artifact filename, or a plain explanation of what failed.
    """
    finding = _read_finding(tool_context)
    if finding is None:
        return "Belum ada temuan di sesi ini. Muat temuan lebih dulu."

    try:
        kb = knowledge_base()
    except DesignKnowledgeBaseError as exc:
        return f"Pustaka desain tidak konsisten dan tidak dapat dipakai: {exc}"

    blok = _selected_blocks(finding, tool_context)
    if not blok:
        return "Reporter belum memilih blok yang punya data. Terbitkan dokumen lebih dulu."

    isi = build_content(blok)
    judul = {b.id: b.judul for b in blok}
    terpilih = [b.id for b in blok if isi.has(b.id)]

    style = PERSONA.get(persona, PERSONA[DEFAULT_PERSONA])
    spec = PresentationSpec.from_dict(
        {
            "style": style,
            "language": "id",
            "emphasis": _read_map(penekanan_json, "emphasis"),
            "form": _read_map(bentuk_json, "form"),
            "accents": _read_map(aksen_json, "accents"),
            "rationale": rationale,
        }
    )
    bawaan = kb.resolve_style(style)["storytelling"].get("emphasis_order") or {}
    spec = normalise(spec, terpilih, bawaan)

    problems = validate(spec, kb, terpilih)
    if problems:
        # Returned to the model rather than raised: a rejected proposal is a normal
        # step, and the model can correct it on the next call.
        return "Spesifikasi ditolak:\n" + "\n".join(f"- {m}" for m in problems)

    prompt = compose_prompt(spec, isi, judul, kb)

    # Jejak ditulis sebelum penggambaran, bukan sesudah: run yang gagal digambar
    # sama perlunya untuk ditelusuri dengan run yang berhasil.
    trail = RunTrail(finding.finding_id)
    trail.record_input(finding, isi, persona, style)

    # Recorded before drawing, so the reviewer inspects what was actually asked for
    # rather than inferring it from the conversation.
    tool_context.state[KUNCI_SPESIFIKASI] = spec.to_dict()
    tool_context.state["prompt_infografis"] = prompt

    try:
        halaman = draw_page(prompt)
    except DrawingUnavailable as exc:
        trail.record_round(1, spec, prompt, review={"drawing_error": str(exc)})
        trail.finish("DRAWING_FAILED", str(exc))
        logger.error("Penggambaran gagal: %s", exc)
        return (
            "Infografis gagal diterbitkan: penggambar tidak tersedia "
            f"({exc}). Sampaikan kegagalan ini apa adanya dan jangan mencoba "
            "menerbitkan ulang — masalahnya di lingkungan, bukan pada temuan "
            "atau pilihan penyajianmu."
        )

    nama = f"infografis-{finding.finding_id}.png"
    try:
        await tool_context.save_artifact(
            filename=nama,
            artifact=types.Part.from_bytes(data=halaman, mime_type="image/png"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Penyimpanan artifact gagal: %s", exc)
        return "Infografis berhasil digambar, tetapi gagal disimpan sebagai artifact."

    trail.record_round(1, spec, prompt, page=halaman)
    jejak = trail.finish("PUBLISHED")
    tool_context.state[KUNCI_JEJAK] = str(jejak.parent)
    # Penilai membuka artifact lewat nama ini. Tanpa baris ini pemeriksaan teks
    # tergambar tidak punya apa pun untuk dibaca, dan diam-diam tidak berjalan.
    tool_context.state[KUNCI_BERKAS_INFOGRAFIS] = nama

    logger.info("Infografis %s tersimpan (%d bita)", nama, len(halaman))
    return (
        f"Infografis tersimpan sebagai {nama} ({len(halaman):,} bita), "
        f"{len(terpilih)} kartu, style {style}. Jejak audit: {jejak.parent}."
    )


def _read_map(mentah: str | None, label: str) -> dict:
    """Read a JSON map argument. Malformed input is ignored, never fatal."""
    if not mentah:
        return {}
    try:
        nilai = json.loads(mentah)
    except json.JSONDecodeError as exc:
        logger.warning("Argumen %s bukan JSON yang sah (%s) — diabaikan", label, exc)
        return {}
    return nilai if isinstance(nilai, dict) else {}


designer_agent = LlmAgent(
    name="designer",
    model=get_settings().vertex_ai_model,
    description=(
        "Memutuskan penekanan visual dan bentuk visual tiap blok, "
        "lalu menerbitkan infografis satu halaman."
    ),
    tools=[ringkas_penyajian, terbitkan_infografis],
    instruction="""
# PERAN
Kamu penyaji visual pada ARKA. Reporter sudah memutuskan blok mana yang masuk
dokumen dan urutannya — **itu bukan wilayahmu dan tidak boleh kamu ubah**.
Keputusanmu satu: blok mana yang mendominasi halaman, dan bentuk visual apa yang
dipakai masing-masing.

# LANGKAH
1. Panggil `ringkas_penyajian` lebih dulu. Jangan menebak isi atau bentuk visual yang tersedia.
2. Timbang penekanannya berdasarkan temuan ini, bukan kebiasaan:
   - Temuan yang perlu eskalasi → `kandidat_penyebab` dominan, supaya pembaca
     segera melihat dua kandidat yang bersaing.
   - Kekuatannya pada pengulangan lintas pabrik → `preseden_lintas_pabrik` dominan.
   - Selisih kekritisan sparepart yang jadi inti → `sparepart_kritis` naik.
   - Keyakinan rendah → jangan membuat halaman seen lebih yakin daripada
     temuannya. Turunkan emphasis kesimpulan, naikkan yang menunjukkan keterbatasan.
3. Pilih bentuk visual hanya bila datanya memenuhi syarat bentuk itu. Ragu →
   kosongkan; teks biasa selalu aman dan tidak pernah menyesatkan.
4. Panggil `terbitkan_infografis`.

# BATAS
- Dilarang memakai em-dash ("—") atau double dash ("--") dalam penjelasan
  maupun argumen. Pakai titik dua, koma, atau tanda hubung biasa.
- Tepat satu blok boleh dominan. Kalau semua penting, tidak ada yang penting.

- Kamu tidak menulis satu pun teks yang tampil di halaman. Seluruhnya disusun kode
  dari temuan. Kamu hanya menyebut pengenal.
- Kamu tidak pernah menyebut, menghitung, membulatkan, atau menerjemahkan angka.
- Spesifikasi yang ditolak bukan kegagalan — baca alasannya, perbaiki, panggil ulang.

# LANGUAGE_NAMES
Bahasa Indonesia, ringkas dan teknis. Sebut blok dengan pengenalnya.
""",
)
