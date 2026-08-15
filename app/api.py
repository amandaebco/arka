"""HTTP surface: the ADK agents, plus a deterministic read API beside them.

An interface needs two different things from ARKA, and serving both through the
agent endpoints was the mistake worth avoiding.

The autonomous chain is the product: `POST /run_sse` runs scout, investigator,
and reporter, takes about a hundred seconds, and costs model calls. That is the
right price for an investigation and the wrong price for painting a screen.

Everything a screen needs first — how many failures are open, which ones the
scout would raise, what the finding says, what the document looks like — is
computed by `app.detection` without a model at all. Exposing it directly means
an interface can show real numbers immediately, and spend the model only when a
human asks for an investigation.

    GET  /api/armada            hasil pemindaian: kasus terbuka, skor, keputusan
    GET  /api/temuan/{tag}      Finding lengkap untuk satu tag
    GET  /api/dokumen/{tag}     dokumen terbit sebagai HTML
    GET  /api/sehat             penyimpanan aktif dan kesegarannya
    POST /run_sse               rantai agent penuh (bawaan ADK)

Serving both from one app also removes a class of bug we already paid for: a
figure on screen and a figure in the memo now come from the same call into the
same deterministic core, so they cannot drift apart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from google.adk.cli.fast_api import get_fast_api_app

from app.detection import store
from app.detection.investigation import rank_screened, screen_case
from app.reporting.dokumen import JENIS, KonteksDokumen
from app.reporting.lencana import lencana_data_uri
from app.reporting.memo import render_dokumen_html

logger = logging.getLogger(__name__)

DIR_AGENT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adk_agents")

# Origin yang boleh memanggil adalah keputusan penyebaran, bukan sesuatu yang
# pantas diam-diam menjadi `*`. Kosong berarti hanya pemanggil non-peramban.
ORIGIN = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()]

app = get_fast_api_app(
    agents_dir=DIR_AGENT,
    allow_origins=ORIGIN or None,
    artifact_service_uri=(
        f"gs://{os.environ['ARTIFACT_GCS_BUCKET']}" if os.getenv("ARTIFACT_GCS_BUCKET") else None
    ),
    web=False,
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
)

KONTEKS = KonteksDokumen(
    nomor="001/ING/VIII/2026",
    kepada="Manajer Keandalan",
    dari="ARKA (Asset Reliability Knowledge Agent)",
    perihal="Preseden kegagalan berulang lintas pabrik",
    penanda_tangan="Head of Reliability",
    jabatan_penanda_tangan="Head of Reliability",
    periode="Agustus 2026",
    unit_penerbit="INGOUDE COMPANY",
    logo=lencana_data_uri("ING"),
)


@app.get("/api/sehat")
async def sehat() -> dict:
    """Penyimpanan mana yang dibaca, dan apakah isinya masih sepadan."""
    from app.bigquery.kesegaran import wajib_segar

    hasil: dict = {"store": store.active_store(), "segar": True, "catatan": ""}
    try:
        await wajib_segar()
    except Exception as exc:  # noqa: BLE001 — status, bukan kegagalan permintaan
        hasil["segar"] = False
        hasil["catatan"] = f"{type(exc).__name__}: {exc}"
    return hasil


# Pemindaian menyentuh BigQuery delapan kali dan berbiaya puluhan detik, sedangkan
# armada tidak berubah dalam hitungan menit. Menghitungnya saat halaman dibuka
# adalah pilihan yang salah dua kali: pengunjung pertama menunggu setengah menit,
# dan instance Cloud Run yang baru bangun mengulanginya lagi dari nol.
#
# Jadi pemindaian dijadwalkan, bukan dipicu tampilan. Hasilnya ditulis ke satu
# berkas dan dibaca langsung; `dihitung_pada` ikut di dalamnya, sehingga umur
# jawaban selalu terlihat pembaca alih-alih disembunyikan di balik kata "cepat".
BERKAS_PINDAI = os.getenv("ARKA_BERKAS_PINDAI", "/tmp/arka-pindai.json")  # noqa: S108
UMUR_CACHE_DETIK = float(os.getenv("ARKA_CACHE_ARMADA", "900"))
_cache: dict = {"pada": 0.0, "isi": None}
_kunci = asyncio.Lock()


def _muat_tersimpan() -> dict | None:
    """Baca pemindaian terjadwal yang terakhir ditulis, kalau ada."""
    try:
        with open(BERKAS_PINDAI, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _simpan(hasil: dict) -> None:
    try:
        with open(BERKAS_PINDAI, "w", encoding="utf-8") as f:
            json.dump(hasil, f)
    except OSError as exc:  # noqa: BLE001 — gagal menyimpan bukan gagal memindai
        logger.warning("Hasil pemindaian tidak tersimpan: %s", exc)


@app.get("/api/armada")
async def armada(segarkan: bool = False) -> dict:
    """Pemindaian armada — keputusan Scout, dihitung tanpa model.

    Yang diabaikan ikut dikembalikan beserta alasannya. Daftar yang hanya memuat
    temuan menarik tidak bisa dibantah; yang memuat penolakan bisa.

    Urutannya: memori, lalu pemindaian terjadwal yang tersimpan, baru menghitung
    sendiri. `?segarkan=true` melewati keduanya.
    """
    async with _kunci:
        umur = time.monotonic() - _cache["pada"]
        if _cache["isi"] is not None and not segarkan and umur < UMUR_CACHE_DETIK:
            return {**_cache["isi"], "umur_detik": round(umur, 1)}

        if not segarkan:
            tersimpan = _muat_tersimpan()
            if tersimpan:
                _cache.update(pada=time.monotonic(), isi=tersimpan)
                return {**tersimpan, "umur_detik": 0.0, "sumber": "terjadwal"}

        hasil = await _pindai()
        _cache.update(pada=time.monotonic(), isi=hasil)
        _simpan(hasil)
        return {**hasil, "umur_detik": 0.0, "sumber": "dihitung"}


@app.post("/api/armada/pindai")
async def pindai_sekarang() -> dict:
    """Titik masuk penjadwal: hitung ulang dan simpan.

    Dipanggil Cloud Scheduler, bukan oleh tampilan. Memisahkan ini dari `GET`
    berarti pemindaian berjalan pada jadwal yang dipilih manusia, dan halaman
    tinggal membaca hasilnya — yang juga membuat klaim "ARKA memindai armada
    tiap pagi tanpa diminta" jadi benar secara harfiah.
    """
    async with _kunci:
        hasil = await _pindai()
        _cache.update(pada=time.monotonic(), isi=hasil)
        _simpan(hasil)
    return {"status": "selesai", "dihitung_pada": hasil["dihitung_pada"],
            "diperiksa": hasil["diperiksa"], "layak": len(hasil["layak"])}


async def _pindai() -> dict:
    async with store.session() as sesi:
        terbuka = await store.find_open_cases(sesi)
        if not terbuka:
            return {"diperiksa": 0, "layak": [], "diabaikan": []}

        dokumen = await store.find_documents(sesi)
        subsistem = store.load_subsystem_map()

        # Satu query per model, bukan per kasus. Dua puluh empat kegagalan
        # terbuka hanya menyentuh enam model, dan kasus historis dipilih menurut
        # model — jadi query yang sama diulang empat kali tanpa hasil berbeda.
        # Perbedaannya bukan penghematan kecil: tiap perjalanan ke BigQuery
        # berbiaya detik, dan halaman yang menunggu semenit tidak akan dibuka
        # dua kali.
        per_model: dict[str, list] = {}
        for model in {k.equipment_model for k in terbuka}:
            per_model[model] = await store.find_historical_cases(sesi, equipment_model=model)

        disaring = []
        for kasus in terbuka:
            historis = [
                h
                for h in per_model.get(kasus.equipment_model, [])
                if h.failure_event_id != kasus.failure_event_id
            ]
            disaring.append(
                screen_case(kasus, store.group_by_cause(historis, dokumen), subsistem)
            )

    baris = [
        {
            "equipment_tag": c.open_case.equipment_tag,
            "pabrik": c.open_case.plant,
            "model": c.open_case.equipment_model,
            # Nama, bukan kode. Kode adalah cara penyimpanan menyebut gejala;
            # yang dibaca manusia di layar harus kalimat yang ia kenali.
            "gejala": list(c.open_case.symptom_names or c.open_case.symptom_codes),
            "terbuka_sejak": c.open_case.started_on.isoformat(),
            "skor": str(c.verdict.top_score),
            "keputusan": c.verdict.decision.value,
            "alasan": c.verdict.reason,
            # Membedakan "sudah dinilai, hasilnya rendah" dari "tidak ada yang
            # bisa dinilai". Keduanya berskor 0,0000, dan tanpa penanda ini
            # pembaca menyimpulkan yang pertama padahal yang terjadi kedua.
            "dapat_dinilai": c.verdict.assessable,
        }
        for c in rank_screened(disaring)
    ]
    layak = [b for b in baris if b["keputusan"] != "ignore"]
    diabaikan = [b for b in baris if b["keputusan"] == "ignore"]
    tanpa_bukti = [b for b in diabaikan if not b["dapat_dinilai"]]
    return {
        "dihitung_pada": datetime.now(UTC).isoformat(timespec="seconds"),
        "store": store.active_store(),
        "diperiksa": len(baris),
        "layak": layak,
        "diabaikan": diabaikan,
        # Cakupan adalah keluaran kelas satu, bukan catatan kaki. Armada yang
        # tidak bisa dinilai adalah pekerjaan yang menunggu, dan menyembunyikannya
        # membuat skor atas sebagian kecil armada terbaca seolah berlaku untuk
        # seluruhnya.
        "cakupan": {
            "diperiksa": len(baris),
            "dapat_dinilai": len(baris) - len(tanpa_bukti),
            "tanpa_bukti": len(tanpa_bukti),
            "persen_dapat_dinilai": (
                round(100.0 * (len(baris) - len(tanpa_bukti)) / len(baris), 1) if baris else 0.0
            ),
        },
    }


@app.get("/api/temuan/{tag:path}")
async def temuan(tag: str) -> dict:
    """Finding lengkap untuk satu tag — kontrak yang sama yang dibaca reporter."""
    from app.detection.temuan_langsung import temuan_untuk

    try:
        hasil = await temuan_untuk(tag)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return hasil.model_dump(mode="json")


@app.get("/api/dokumen/{tag:path}", response_class=HTMLResponse)
async def dokumen(tag: str, jenis: str = "memo") -> HTMLResponse:
    """Dokumen terbit sebagai HTML, dirakit dari temuan yang sama.

    HTML, bukan PDF: sebuah antarmuka menampilkannya langsung, dan PDF hanya
    perlu ada ketika dokumen itu dikirim ke manusia di luar layar.
    """
    if jenis not in JENIS:
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal: {jenis}")

    from app.detection.temuan_langsung import temuan_untuk

    try:
        hasil = await temuan_untuk(tag)
        html = render_dokumen_html(hasil, jenis=jenis, konteks=KONTEKS)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(html)
