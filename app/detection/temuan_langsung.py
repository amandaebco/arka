"""Build a `Finding` for a live open failure, outside an agent session.

The investigator assembles findings inside an ADK tool, which is the right place
for it — but it means the only way to obtain a real finding was to run a model.
The publication scripts therefore fell back to `finding_contoh()`, and every
document and infographic ever rendered for review carried the sample's numbers
rather than the fleet's.

That gap is not cosmetic. A memo shown beside a published score has to be the
memo that score produced, or the pair invites exactly the doubt the citation
discipline exists to remove.

This module walks the same deterministic path the investigator's tool walks, and
stops where the tool would hand over to a model. Nothing here calls Gemini.
"""

from __future__ import annotations

import logging
from datetime import date

from app.detection import store
from app.detection.investigation import build_finding, score_candidates
from app.reporting.finding import Finding, LangkahPenalaran

logger = logging.getLogger(__name__)


async def temuan_untuk(equipment_tag: str | None = None) -> Finding:
    """Assemble a finding from the graph.

    With no tag, takes the highest-scoring open failure — the same case Scout
    would raise on its own, which is what a demo should show.
    """
    async with store.session() as sesi:
        kasus = await store.find_open_cases(sesi)
        if not kasus:
            raise RuntimeError("Tidak ada kegagalan terbuka di penyimpanan aktif.")

        if equipment_tag:
            cocok = [k for k in kasus if k.equipment_tag == equipment_tag]
            if not cocok:
                tersedia = ", ".join(sorted(k.equipment_tag for k in kasus)[:8])
                raise RuntimeError(f"{equipment_tag} tidak terbuka. Yang terbuka: {tersedia}")
            kasus_terpilih = cocok[0]
        else:
            kasus_terpilih = await _paling_kuat(sesi, kasus)

        return await _rakit(sesi, kasus_terpilih)


async def _paling_kuat(sesi, kasus: list):
    """Pick the case whose leading candidate scores highest."""
    peta = store.load_subsystem_map()
    dokumen = await store.find_documents(sesi)
    terbaik, skor_terbaik = kasus[0], None
    for k in kasus:
        historis = await store.find_historical_cases(
            sesi, equipment_model=k.equipment_model, exclude_event_id=k.failure_event_id
        )
        if not historis:
            continue
        dinilai = score_candidates(k, store.group_by_cause(historis, dokumen), peta)
        if dinilai and (skor_terbaik is None or dinilai[0].score.total > skor_terbaik):
            terbaik, skor_terbaik = k, dinilai[0].score.total
    return terbaik


async def _rakit(sesi, kasus) -> Finding:
    jejak = [
        LangkahPenalaran(
            urutan=1,
            aksi=f"Membaca gejala kegagalan terbuka pada {kasus.equipment_tag}",
            hasil=f"{len(kasus.symptom_codes)} gejala tercatat",
            jumlah_simpul=len(kasus.symptom_codes),
        )
    ]

    historis = await store.find_historical_cases(
        sesi, equipment_model=kasus.equipment_model, exclude_event_id=kasus.failure_event_id
    )
    jejak.append(
        LangkahPenalaran(
            urutan=2,
            aksi=f"Menelusuri kasus tuntas pada model {kasus.equipment_model}",
            hasil=f"{len(historis)} kasus dengan penyebab terverifikasi",
            jumlah_simpul=len(historis),
        )
    )

    dokumen = await store.find_documents(sesi)
    kandidat = store.group_by_cause(historis, dokumen)
    dinilai = score_candidates(kasus, kandidat, store.load_subsystem_map())
    pabrik = sorted({c.plant for k in kandidat for c in k.historical_cases})
    jejak.append(
        LangkahPenalaran(
            urutan=3,
            aksi="Menghitung skor kemiripan secara deterministik",
            hasil=f"Preseden berasal dari pabrik: {', '.join(pabrik)}",
            jumlah_simpul=len(pabrik),
        )
    )

    parts = await store.find_spare_parts(sesi)
    jendela = await store.find_next_maintenance(sesi, kasus.equipment_tag)
    sisa = (jendela - date.today()).days if jendela else None

    temuan, vonis = build_finding(
        kasus,
        dinilai,
        spare_parts=parts,
        trail=jejak,
        days_until_maintenance=sisa,
    )
    logger.info(
        "temuan %s dirakit: %s", temuan.finding_id, vonis.decision.value
    )
    return temuan
