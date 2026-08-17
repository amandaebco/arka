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
from typing import Annotated

from fastapi import HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from google.adk.cli.fast_api import get_fast_api_app
from sqlalchemy import text

from app.core.config import get_settings
from app.detection import store
from app.detection.investigation import rank_screened, screen_case
from app.detection.scoring import THRESHOLD_AMBIGUITY, THRESHOLD_IGNORE, THRESHOLD_REPORT
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

_NAMA_GRAPH = get_settings().age_graph_name

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

        # Ukuran armada, supaya "148 kasus" punya penyebut. Tanpa itu pembaca
        # tidak tahu apakah 148 berarti hampir semuanya atau sebagian kecil --
        # dan justru perbandingan itu yang menjelaskan kenapa penyaringan perlu.
        armada_total = (await sesi.execute(text("SELECT count(*) FROM equipment"))).scalar() or 0

        # Kegagalan yang sudah tuntas bukan sisa, melainkan bahan pembandingnya:
        # setiap preseden lintas pabrik datang dari sini. Menyebut jumlahnya
        # membuat "148 terbuka" punya konteks, dan sekaligus memperlihatkan
        # dari mana bukti yang dipakai menilai berasal.
        tuntas = (
            await sesi.execute(text("SELECT count(*) FROM failure_events WHERE status = 'closed'"))
        ).scalar() or 0

        if not terbuka:
            return {
                "diperiksa": 0,
                "armada": armada_total,
                "kegagalan_tuntas": int(tuntas),
                "layak": [],
                "diabaikan": [],
            }

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
            # Dasar skornya, bukan cuma hasilnya. Layar yang menyebut 91% tanpa
            # menyebut dibanding apa menuntut pembaca percaya begitu saja --
            # dan preseden inilah satu-satunya alasan angka itu ada.
            "preseden": sum(len(k.evidence.historical_cases) for k in c.scored),
            "pabrik_preseden": len(
                {h.plant for k in c.scored for h in k.evidence.historical_cases}
            ),
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
        # Ambangnya ikut dikirim, bukan ditulis ulang di tampilan: kebijakan yang
        # disalin ke dua tempat akan berbeda pada hari salah satunya diubah, dan
        # layar yang menyebut ambang berbeda dari yang dipakai mesin lebih buruk
        # daripada layar yang tidak menyebutnya sama sekali.
        "ambang": {
            "laporkan": str(THRESHOLD_REPORT),
            "abaikan": str(THRESHOLD_IGNORE),
            "ambigu": str(THRESHOLD_AMBIGUITY),
        },
        # Kegagalan terbuka, bukan mesin: satu mesin bisa punya lebih dari satu.
        # Pada data sekarang keduanya kebetulan sama, dan menyamakannya di layar
        # akan menjadikan kebetulan itu tampak sebagai aturan.
        "armada": armada_total,
        "kegagalan_tuntas": int(tuntas),
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


@app.get("/api/graph")
async def graph() -> dict:
    """Ukuran graph AGE — dihitung, bukan ditulis.

    Angka di layar yang tidak bisa ditelusuri ke penyimpanan adalah angka yang
    diam-diam basi: proyeksi tumbuh, tulisan di kode tidak. Dihitung dari tabel
    label AGE, bukan dengan `MATCH (n)`, karena yang kedua memindai seluruh
    graph untuk pertanyaan yang jawabannya sudah ada di katalog.

    Label yang kosong tidak ikut dihitung sebagai label: ontologi menyediakan
    tempat untuk konsep yang datanya belum ada, dan menghitungnya akan
    melaporkan kekayaan yang belum tentu terisi.
    """
    sql_hitung = text("""
        SELECT l.kind::text AS jenis, count(*) AS label, coalesce(sum(x.n), 0) AS isi
        FROM ag_catalog.ag_label l
        JOIN ag_catalog.ag_graph g ON g.graphid = l.graph
        CROSS JOIN LATERAL (
            SELECT n_live_tup AS n
            FROM pg_stat_user_tables
            WHERE schemaname = g.name::text AND relname = l.name::text
        ) x
        WHERE g.name::text = :graph AND x.n > 0
        GROUP BY l.kind
    """)
    async with store.session() as sesi:
        try:
            baris = (await sesi.execute(sql_hitung, {"graph": _NAMA_GRAPH})).all()
        except Exception as exc:  # noqa: BLE001 — status, bukan kegagalan permintaan
            return {"tersedia": False, "catatan": f"{type(exc).__name__}: {exc}"}

    hitung = {r.jenis: (int(r.label), int(r.isi)) for r in baris}
    label_v, node = hitung.get("v", (0, 0))
    label_e, edge = hitung.get("e", (0, 0))
    return {
        "tersedia": node > 0,
        "graph": _NAMA_GRAPH,
        "node": node,
        "edge": edge,
        "label_node": label_v,
        "label_edge": label_e,
    }


@app.get("/api/korpus")
async def korpus() -> dict:
    """Basis bukti: dokumen dan potongan yang bisa dirujuk sitasi.

    Ini angka yang menopang klaim paling penting ARKA. Sebuah memo bersitasi
    hanya sekuat korpus di belakangnya, dan korpus yang tidak pernah disebut
    ukurannya menuntut pembaca percaya begitu saja.

    Potongan **terindeks** dihitung terpisah dari potongan yang ada: indeks yang
    tertinggal di belakang dokumennya adalah kegagalan diam -- pencarian tetap
    menjawab, hanya tidak dari seluruh yang tersedia.
    """
    async with store.session() as sesi:
        try:
            dokumen = (await sesi.execute(text("SELECT count(*) FROM documents"))).scalar() or 0
            potongan = (
                await sesi.execute(text("SELECT count(*) FROM document_chunks"))
            ).scalar() or 0
            terindeks = (
                await sesi.execute(text("SELECT count(*) FROM document_chunks_embedded"))
            ).scalar() or 0
        except Exception as exc:  # noqa: BLE001 — status, bukan kegagalan permintaan
            return {"tersedia": False, "catatan": f"{type(exc).__name__}: {exc}"}

    return {
        "tersedia": dokumen > 0,
        "dokumen": int(dokumen),
        "potongan": int(potongan),
        "terindeks": int(terindeks),
        # Indeks yang tidak sepadan dengan korpusnya patut terlihat, bukan
        # disimpulkan sendiri oleh pembaca dari dua angka yang kebetulan beda.
        "indeks_lengkap": int(terindeks) >= int(potongan),
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


@app.get("/api/aktivitas")
async def aktivitas(event: Annotated[list[str], Query()] = ()) -> dict:
    """Langkah perawatan yang tercatat untuk kegagalan tertentu — untuk tampilan.

    Sengaja **tidak** melewati `app/detection`: paket itu dijaga tes agar tidak
    pernah membaca `maintenance_activities`, karena tabel itu tidak boleh punya
    jalur ke angka yang tercetak di memo. Di sini ia dibaca sebagai keterangan
    layar saja — tidak menyentuh `Finding`, tidak menyentuh skor.

    Args:
        event: `failure_event_id` yang ingin dilihat aktivitasnya.
    """
    if not event:
        return {"aktivitas": {}}

    sql = text("""
        SELECT wfe.failure_event_id::text AS event_id,
               a.activity_code, a.activity_type, a.description, a.result
        FROM work_order_failure_events wfe
        JOIN work_orders wo ON wo.id = wfe.work_order_id
        JOIN maintenance_activities a ON a.work_order_id = wo.id
        WHERE wfe.failure_event_id = ANY(:ids)
        ORDER BY wfe.failure_event_id, a.sequence_number
    """)
    async with store.session() as sesi:
        try:
            baris = (await sesi.execute(sql, {"ids": list(event)})).all()
        except Exception as exc:  # noqa: BLE001 — keterangan layar, bukan jalur kritis
            logger.warning("aktivitas tidak terbaca: %s", exc)
            return {"aktivitas": {}}

    hasil: dict[str, list[dict]] = {}
    for r in baris:
        hasil.setdefault(r.event_id, []).append(
            {
                "kode": r.activity_code,
                "jenis": r.activity_type,
                "deskripsi": r.description,
                "hasil": r.result,
            }
        )
    return {"aktivitas": hasil}


@app.get("/api/poster")
async def poster() -> Response:
    """Poster infografis terbaru — gambar, bukan halaman.

    Poster adalah keluaran designer: halamannya digambar model, lalu dibaca
    ulang penilai lewat vision. Ia PNG karena memang gambar, dan menyajikannya
    sebagai HTML akan menyamarkan asal-usulnya.

    Berkas diambil dari jejak render terakhir di `out/infografis/`. Kalau belum
    pernah dirender, katakan begitu — jangan menampilkan halaman deterministik
    sebagai gantinya, karena keduanya lahir dari jalur yang berbeda.
    """
    akar = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "infografis"
    )
    if not os.path.isdir(akar):
        raise HTTPException(status_code=404, detail="Belum ada poster yang dirender.")

    jejak = sorted(
        (d for d in os.listdir(akar) if os.path.isdir(os.path.join(akar, d))), reverse=True
    )
    for d in jejak:
        for nama in sorted(os.listdir(os.path.join(akar, d)), reverse=True):
            if nama.endswith("-page.png"):
                berkas = os.path.join(akar, d, nama)
                with open(berkas, "rb") as f:
                    isi = f.read()
                return Response(
                    content=isi,
                    media_type="image/png",
                    headers={"X-Arka-Jejak": d},
                )
    raise HTTPException(status_code=404, detail="Belum ada poster yang dirender.")


@app.get("/api/dokumen-pdf/{tag:path}")
async def dokumen_pdf(tag: str, jenis: str = "memo") -> Response:
    """Dokumen yang sama, sebagai PDF A4 — bentuk yang dikirim ke manusia.

    Dirender Chromium dari HTML yang sama persis, jadi berkas unduhan dan layar
    tidak punya jalan untuk berbeda. Kalau peramban tidak terpasang di
    lingkungan ini, kegagalannya dikatakan apa adanya: memberi HTML bernama
    `.pdf` akan membuat penerima mengira ia memegang dokumen resmi.
    """
    if jenis not in JENIS:
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal: {jenis}")

    from app.detection.temuan_langsung import temuan_untuk
    from app.reporting.memo import render_dokumen_pdf

    try:
        hasil = await temuan_untuk(tag)
        pdf = await render_dokumen_pdf(hasil, jenis=jenis, konteks=KONTEKS)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — peramban hilang, bukan salah pemanggil
        raise HTTPException(
            status_code=503, detail=f"PDF tidak dapat dirender: {type(exc).__name__}"
        ) from exc

    nama = f"{tag.replace('/', '-')}-{jenis}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


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
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Langkah perawatan yang tercatat untuk tiap preseden. Dibaca di sini, bukan
    # di `app/detection`: paket itu dijaga tes agar tabel aktivitas tidak punya
    # jalur ke angka memo. Lewat konteks, ia sampai ke halaman sebagai keterangan
    # dan tidak pernah ikut dihitung.
    langkah = await _langkah_perawatan(hasil)
    konteks = KONTEKS.model_copy(update={"langkah_perawatan": langkah})
    return HTMLResponse(render_dokumen_html(hasil, jenis=jenis, konteks=konteks))


async def _langkah_perawatan(temuan) -> tuple[dict, ...]:
    """Aktivitas per preseden, dipetakan ke pabrik dan tag yang mengerjakannya."""
    ids = [p.failure_event_id for p in temuan.preseden if p.failure_event_id]
    if not ids:
        return ()

    hasil = await aktivitas(event=ids)
    per_event = hasil.get("aktivitas", {})
    keluar: list[dict] = []
    for p in temuan.preseden:
        for a in per_event.get(p.failure_event_id, []):
            keluar.append(
                {
                    "pabrik": p.pabrik,
                    "equipment_tag": p.equipment_tag,
                    "jenis": a["jenis"],
                    "kode": a["kode"],
                    "deskripsi": a["deskripsi"],
                    "hasil": a.get("hasil"),
                }
            )
    return tuple(keluar)
