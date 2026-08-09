"""Agent `penilai` — pemeriksa mutu dokumen sebelum diserahkan ke manusia.

Dipasang sebagai `LoopAgent`: reporter menerbitkan, penilai memeriksa, dan bila
ada cacat, reporter menerbitkan ulang dengan masukan itu. **Maksimum tiga
putaran** — batas keras, bukan saran. Dokumen yang belum sempurna tetap lebih
berguna daripada agent yang berputar tanpa henti menjelang demo.

Pembagian tugas mengikuti prinsip yang sama seperti di tempat lain:

* **Kode** yang memeriksa hal-hal objektif — angka bocor di narasi, blok kosong
  yang diminta, kelengkapan surat yang belum diisi, sitasi yang tidak ada.
  Pemeriksaan begini tidak boleh diserahkan ke model: jawabannya pasti.
* **Model** yang menimbang hal-hal yang memang butuh pertimbangan — apakah
  urutan blok masuk akal bagi pembaca, apakah narasinya menjelaskan atau cuma
  mengulang tabel, apakah dokumen ini layak dikirim.

Penilai tidak pernah menyunting dokumen. Ia menuliskan masukan ke state, dan
reporter yang memperbaiki — supaya keputusan blok tetap milik satu agent.

Catatan: `LoopAgent` sudah ditandai usang di ADK 2.x demi `google.adk.workflow`.
Ia tetap dipakai di sini karena API penggantinya jauh lebih berat untuk kebutuhan
sesederhana ini, dan penggantian menjelang tenggat bukan risiko yang sepadan.
Kalau ARKA berlanjut setelah hackathon, migrasi ini yang pertama dikerjakan.
"""

from __future__ import annotations

import logging
import re

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from app.agents.designer import (
    KUNCI_BERKAS_INFOGRAFIS,
    KUNCI_SPESIFIKASI,
    designer_agent,
    knowledge_base,
)
from app.agents.reporter import KUNCI_TEMUAN, reporter_agent
from app.core.config import get_settings
from app.designer.content import build_content, is_composed_label
from app.designer.inspection import (
    InspectionUnavailable,
    authorised_strings,
    read_page_text,
    unauthorised_text,
)
from app.reporting.blocks import susun_blok
from app.reporting.finding import Finding
from app.reporting.narasi import memuat_angka

logger = logging.getLogger(__name__)

# Masukan penilai untuk putaran berikutnya. Reporter membacanya lewat prompt.
KUNCI_MASUKAN = "masukan_qa"

# Batas putaran. Tiga sudah cukup: satu untuk terbit, satu untuk perbaikan,
# satu cadangan. Lebih dari itu biasanya pertanda cacatnya bukan di dokumen.
MAKS_PUTARAN = 3


# Teks yang selalu boleh tampil meski bukan isi temuan: penanda baku halaman.
TEKS_BAKU_HALAMAN = (
    "Keyakinan", "Eskalasi", "Gejala", "Penyebab teratas",
    "Perlu putusan manusia", "Langkah", "indikasi awal", "sudah cukup kuat",
    "masih perlu dipastikan", "Pabrik", "Model", "jam", "HIGH", "TINGGI",
)


def _temuan(tool_context: ToolContext) -> Finding | None:
    mentah = tool_context.state.get(KUNCI_TEMUAN)
    if not mentah:
        return None
    try:
        return Finding.model_validate(mentah)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Temuan tidak terbaca saat pemeriksaan: %s", exc)
        return None


async def periksa_dokumen(tool_context: ToolContext) -> str:
    """Memeriksa dokumen terakhir terhadap syarat mutu yang objektif.

    Panggil ini lebih dulu, sebelum menilai hal yang butuh pertimbangan.
    Hasilnya fakta, bukan pendapat — jangan dibantah, cukup diteruskan ke
    reporter sebagai perbaikan yang harus dikerjakan.

    Args:
        tool_context: Disuntikkan ADK.

    Returns:
        Daftar cacat yang ditemukan, atau pernyataan bahwa semuanya lulus.
    """
    finding = _temuan(tool_context)
    if finding is None:
        return "Tidak ada temuan di sesi — tidak ada yang bisa diperiksa."

    cacat: list[str] = []

    # 1. Sitasi. Dasar keterlacakan; tanpa ini dokumen memang tidak boleh ada.
    if not finding.semua_sitasi():
        cacat.append("Temuan tidak memuat sitasi — dokumen seharusnya tidak diterbitkan.")

    # 2. Narasi yang menyelundupkan angka. Penyaring sudah membuangnya, tetapi
    #    reporter tetap perlu tahu agar tidak mengulanginya.
    narasi = tool_context.state.get("narasi_terakhir") or {}
    for id_blok, teks in narasi.items():
        if isinstance(teks, str) and memuat_angka(teks):
            cacat.append(
                f"Narasi blok `{id_blok}` memuat angka — angka hanya boleh dari tabel."
            )

    # 3. Blok yang diminta padahal kosong, atau id yang tidak dikenal.
    # `BLOK_WAJIB` tidak diperiksa di sini: `pilih_blok` menyisipkannya paksa,
    # jadi reporter yang tidak menyebutnya bukan sedang berbuat salah. Memeriksanya
    # justru memicu putaran perbaikan untuk cacat yang tidak pernah ada.
    blok = susun_blok(finding)
    urutan = tool_context.state.get("urutan_terakhir") or []
    if urutan:
        for id_blok in urutan:
            if id_blok in blok and not blok[id_blok].tersedia:
                cacat.append(f"Blok `{id_blok}` diminta padahal tidak punya data.")
            if id_blok not in blok:
                cacat.append(f"Id blok `{id_blok}` tidak dikenal.")

    # 4. Eskalasi harus terlihat sejak awal dokumen.
    if finding.perlu_eskalasi and urutan:
        posisi = urutan.index("kandidat_penyebab") if "kandidat_penyebab" in urutan else 99
        if posisi > 1:
            cacat.append(
                "Temuan ini perlu eskalasi, tetapi `kandidat_penyebab` tidak diletakkan "
                "di awal — pembaca harus segera melihat kandidat yang bersaing ketat."
            )

    # 5. Kelengkapan surat untuk jenis yang menuntutnya.
    jenis = tool_context.state.get("jenis_terakhir")
    konteks = tool_context.state.get("konteks_terakhir") or {}
    if jenis == "nota_dinas":
        for medan in ("kepada", "dari", "perihal"):
            if not konteks.get(medan):
                cacat.append(f"Nota dinas tanpa `{medan}` — kelengkapan surat wajib diisi.")

    if not cacat:
        return "LULUS — tidak ada cacat objektif pada dokumen terakhir."

    logger.info("Pemeriksaan menemukan %d cacat", len(cacat))
    return "Cacat yang ditemukan:\n" + "\n".join(f"- {c}" for c in cacat)


async def periksa_infografis(tool_context: ToolContext) -> str:
    """Memeriksa infografis terakhir terhadap syarat mutu yang objektif.

    Panggil ini ketika yang sedang dinilai adalah infografis, bukan dokumen.
    Pemeriksaan terberatnya adalah kesetiaan teks: setiap string yang dikirim ke
    penggambar harus dapat ditemukan pada temuan. Ini imbangan kedua dari
    pengecualian Prinsip I (Constitution 1.2.0) — tanpa pemeriksaan ini,
    pengecualian itu tidak punya penjaga.

    Args:
        tool_context: Disuntikkan ADK.

    Returns:
        Daftar cacat yang ditemukan, atau pernyataan bahwa semuanya lulus.
    """
    finding = _temuan(tool_context)
    if finding is None:
        return "Tidak ada temuan di sesi — tidak ada yang bisa diperiksa."

    spec = tool_context.state.get(KUNCI_SPESIFIKASI)
    if not spec:
        return "Belum ada infografis yang diterbitkan pada sesi ini."

    cacat: list[str] = []

    # 1. Kesetiaan teks. Yang dibandingkan adalah isi kanvas hasil penyusunan
    #    deterministik terhadap temuan — bukan gambar terhadap kanvas. Kalau ada
    #    string yang tidak berasal dari temuan, ia lahir di lapisan penyusun, dan
    #    di situlah cacatnya harus diperbaiki.
    blok = [b for b in susun_blok(finding).values() if b.tersedia]
    isi = build_content(blok)
    sumber = _kumpulan_teks_temuan(finding)
    for id_blok in spec.get("order") or []:
        for item in isi.items(id_blok):
            # Label yang disusun lapisan penyusun menamai peran, bukan nilai —
            # ia memang tidak ada di temuan, dan itu bukan karangan.
            kandidat_teks = [item.text]
            if item.label and not is_composed_label(item.label):
                kandidat_teks.append(item.label)
            for nilai in kandidat_teks:
                if nilai and not _berasal_dari(nilai, sumber):
                    cacat.append(
                        f"Teks pada blok `{id_blok}` tidak ditemukan di temuan: "
                        f"“{nilai[:60]}…”"
                    )

    # 2. Setiap nilai yang digambar harus juga tertulis. Imbangan pertama.
    for id_blok in spec.get("order") or []:
        for item in isi.items(id_blok):
            if item.quantity and not item.value:
                cacat.append(f"Blok `{id_blok}` membawa kuantitas tanpa nilai tertulis.")

    # 3. Tepat satu blok dominan. Halaman tanpa titik fokus tidak punya pintu masuk.
    emphasis = spec.get("emphasis") or {}
    dominan = [b for b, t in emphasis.items() if t == "dominant"]
    if len(dominan) > 1:
        cacat.append(f"Ada {len(dominan)} blok dominan — hanya boleh satu.")
    if not dominan:
        cacat.append("Tidak ada blok dominan — halaman tidak punya titik fokus.")

    # 4. Eskalasi harus terlihat, sama seperti pada dokumen.
    if finding.perlu_eskalasi:
        posisi = (spec.get("order") or []).index("kandidat_penyebab") if (
            "kandidat_penyebab" in (spec.get("order") or [])
        ) else 99
        if posisi > 2:
            cacat.append(
                "Temuan ini perlu eskalasi, tetapi `kandidat_penyebab` tidak berada "
                "di bagian awal halaman."
            )

    # 5. Blok tanpa isi tidak boleh diminta tampil.
    for id_blok in spec.get("order") or []:
        if not isi.has(id_blok):
            cacat.append(f"Blok `{id_blok}` diminta tampil padahal tidak punya isi.")

    if not cacat:
        return "LULUS — tidak ada cacat objektif pada infografis terakhir."

    logger.info("Pemeriksaan infografis menemukan %d cacat", len(cacat))
    return "Cacat yang ditemukan:\n" + "\n".join(f"- {c}" for c in cacat)


def _kumpulan_teks_temuan(finding: Finding) -> str:
    """Seluruh teks pada temuan, digabung untuk pemeriksaan asal-usul string."""
    bagian = [finding.equipment_tag, finding.pabrik, finding.model_equipment or ""]
    bagian += list(finding.gejala)
    bagian += [finding.alasan_eskalasi or ""]
    for k in finding.kandidat:
        bagian += [k.nama, k.deskripsi or ""]
    for p in finding.preseden:
        bagian += [p.pabrik, p.equipment_tag, p.penyelesaian or ""]
    for m in finding.rantai_kausal:
        bagian += [m.peran, m.label, m.detail or ""]
    for s in finding.sparepart:
        bagian += [s.part_number, s.nama]
    for j in finding.jejak_penalaran:
        bagian += [j.aksi, j.hasil]
    for r in finding.rekomendasi:
        bagian += [r.tindakan, r.dasar or ""]
    for c in finding.semua_sitasi():
        bagian += [c.judul, c.tipe_dokumen, c.lokator or "", c.kutipan or ""]
    return "\n".join(b for b in bagian if b).casefold()


def _berasal_dari(nilai: str, sumber: str) -> bool:
    """Apakah sebuah string berasal dari temuan.

    Label yang disusun lapisan penyusun (mis. "Gejala", "Langkah 2") tidak ada di
    temuan sebagai teks utuh, jadi yang diperiksa adalah kata-kata isinya. Sebuah
    string dianggap sah bila seluruh kata panjangnya muncul di temuan — cukup
    ketat untuk menangkap kalimat karangan, cukup longgar untuk memaafkan label
    struktural.
    """
    kata = [k for k in re.findall(r"[\w-]+", nilai.casefold()) if len(k) > 3]
    if not kata:
        return True
    return all(k in sumber for k in kata)



async def periksa_teks_tergambar(tool_context: ToolContext) -> str:
    """Membaca infografis yang sudah tergambar dan menandai teks yang tidak disetujui.

    Pemeriksaan lain membandingkan isi kanvas terhadap temuan — satu tahap
    **sebelum** penggambaran. Alat ini membaca gambarnya sendiri, karena justru
    tahap penggambaran itulah yang dikecualikan Prinsip I, dan tanpa alat ini
    pengecualian tersebut tidak punya penjaga.

    Args:
        tool_context: Disuntikkan ADK.

    Returns:
        Daftar teks yang tampil tetapi tidak berasal dari isi kanvas, atau
        pernyataan bahwa seluruh teks tergambar memang disetujui.
    """
    finding = _temuan(tool_context)
    if finding is None:
        return "Tidak ada temuan di sesi — tidak ada yang bisa diperiksa."

    nama = tool_context.state.get(KUNCI_BERKAS_INFOGRAFIS)
    if not nama:
        return "Belum ada infografis yang tergambar pada sesi ini."

    try:
        bagian = await tool_context.load_artifact(filename=nama)
    except Exception as exc:  # noqa: BLE001
        return f"Artifact `{nama}` tidak dapat dibaca: {exc}"
    if bagian is None or not getattr(bagian, "inline_data", None):
        return f"Artifact `{nama}` tidak memuat gambar."

    # Daftar teks yang boleh tampil disusun di satu tempat — dipakai bersama
    # skrip pengembangan, supaya tidak ada dua versi yang berbeda diam-diam.
    blok = [b for b in susun_blok(finding).values() if b.tersedia]
    isi = build_content(blok)
    subjudul = ""
    spec_style = (tool_context.state.get(KUNCI_SPESIFIKASI) or {}).get("style")
    if spec_style:
        try:
            subjudul = knowledge_base().get_style(spec_style)["presentation"]["reference"]
        except Exception:  # noqa: BLE001 — subjudul opsional, bukan syarat periksa
            subjudul = ""
    disetujui = authorised_strings(isi, [b.judul for b in blok], subjudul)

    try:
        tergambar = read_page_text(bagian.inline_data.data)
    except InspectionUnavailable as exc:
        # Pembaca yang gagal tidak boleh terlihat seperti halaman yang bersih.
        logger.error("Pembacaan halaman gagal: %s", exc)
        return (
            f"Halaman tidak dapat dibaca ({exc}). Jangan menyatakan infografis "
            "layak kirim: pemeriksaan teks tergambar belum pernah berhasil."
        )

    asing = unauthorised_text(tergambar, disetujui)
    if not asing:
        return (
            f"LULUS — {len(tergambar)} teks terbaca pada halaman, seluruhnya "
            "berasal dari isi kanvas."
        )

    logger.info("Teks tak disetujui pada halaman: %d", len(asing))
    return "Teks yang tampil tetapi tidak berasal dari isi kanvas:\n" + "\n".join(
        f"- “{a}”" for a in asing
    )


def selesai(alasan: str, tool_context: ToolContext) -> str:
    """Menyatakan dokumen layak kirim dan menghentikan putaran perbaikan.

    Panggil hanya bila tidak ada lagi yang perlu diperbaiki.

    Args:
        alasan: Satu kalimat mengapa dokumen dinyatakan layak.
        tool_context: Disuntikkan ADK.

    Returns:
        Konfirmasi penghentian.
    """
    tool_context.actions.escalate = True
    tool_context.state[KUNCI_MASUKAN] = ""
    logger.info("Penilai menghentikan putaran: %s", alasan)
    return f"Dokumen dinyatakan layak kirim. {alasan}"


def minta_perbaikan(masukan: str, tool_context: ToolContext) -> str:
    """Meneruskan perbaikan yang harus dikerjakan reporter pada putaran berikutnya.

    Args:
        masukan: Perbaikan konkret, satu per baris. Sebutkan blok atau bagian
            yang dimaksud, bukan penilaian umum seperti "kurang bagus".
        tool_context: Disuntikkan ADK.

    Returns:
        Konfirmasi bahwa masukan tersimpan.
    """
    tool_context.state[KUNCI_MASUKAN] = masukan
    logger.info("Penilai meminta perbaikan")
    return "Masukan diteruskan ke reporter untuk putaran berikutnya."


penilai_agent = LlmAgent(
    name="penilai",
    model=get_settings().vertex_ai_model,
    description="Memeriksa mutu dokumen investigasi sebelum diserahkan ke manusia.",
    tools=[periksa_dokumen, selesai, minta_perbaikan],
    instruction=f"""
# PERAN
Kamu penilai mutu dokumen pada ARKA. Kamu **tidak menyunting dokumen** dan tidak
menerbitkan apa pun. Kamu memeriksa, lalu memutuskan satu hal: dokumen ini layak
dikirim ke manusia, atau harus diperbaiki dulu.

# LANGKAH
1. Panggil `periksa_dokumen`. Hasilnya fakta, bukan pendapat — jangan dibantah.
3. Di atas kedua hasil itu, timbang hal yang memang butuh pertimbangan:
   - Apakah urutan blok masuk akal bagi pembaca yang sibuk?
   - Apakah narasi menjelaskan makna, atau cuma mengulang isi tabel?
   - Untuk temuan yang perlu eskalasi: apakah pembaca segera paham bahwa ada
     keputusan yang menunggu dia?
3. Putuskan:
   - Tidak ada cacat objektif dan pertimbanganmu tidak menemukan masalah berarti
     → panggil `selesai`.
   - Ada yang perlu diperbaiki → panggil `minta_perbaikan` dengan perbaikan yang
     konkret dan bisa dikerjakan.

# BATAS
Putaran perbaikan dibatasi {MAKS_PUTARAN} kali. Jangan menahan dokumen demi
kesempurnaan gaya bahasa — dokumen yang tertahan tidak menolong siapa pun.
Tahan hanya bila ada yang benar-benar keliru atau menyesatkan.

Kamu juga tidak pernah menyebut angka. Kalau reporter salah menaruh angka di
narasi, katakan "narasi blok X memuat angka", bukan angkanya berapa.

# BAHASA
Bahasa Indonesia, ringkas, spesifik. Sebut blok atau bagian yang kamu maksud.
""",
)


# Penilai infografis. Keputusannya sama — layak kirim atau belum — sehingga
# `selesai` dan `minta_perbaikan` dipakai bersama. Yang berbeda hanya rubriknya,
# dan itu perbedaan alat, bukan perbedaan peran. Memecahnya jadi dua agent akan
# menduplikasi keputusan yang sama.
penilai_visual_agent = LlmAgent(
    name="penilai_visual",
    model=get_settings().vertex_ai_model,
    description="Memeriksa mutu infografis sebelum diserahkan ke manusia.",
    tools=[periksa_infografis, periksa_teks_tergambar, selesai, minta_perbaikan],
    instruction=f"""
# PERAN
Kamu penilai mutu infografis pada ARKA. Kamu **tidak menyunting** dan tidak
menerbitkan apa pun. Kamu memeriksa, lalu memutuskan satu hal: halaman ini layak
dikirim ke manusia, atau harus disusun ulang dulu.

# LANGKAH
1. Panggil `periksa_infografis` — memeriksa isi kanvas terhadap temuan.
2. Panggil `periksa_teks_tergambar` — membaca gambarnya dan menandai teks yang
   tidak berasal dari isi kanvas. Ini pemeriksaan yang paling menentukan:
   penggambar bisa menambahkan chip atau label yang tidak pernah diminta.
3. Di atas kedua hasil itu, timbang hal yang memang butuh pertimbangan:
   - Apakah blok yang dominan memang yang paling penting bagi pembaca temuan ini?
   - Untuk temuan berkeyakinan rendah: apakah halaman terlihat lebih yakin
     daripada temuannya? Itu cacat, bukan gaya.
   - Apakah bentuk visual yang dipilih menolong, atau justru menambah beban baca?
4. Putuskan:
   - Kedua pemeriksaan lulus dan pertimbanganmu tidak menemukan masalah berarti
     → panggil `selesai`.
   - Ada yang perlu diperbaiki → panggil `minta_perbaikan` dengan perbaikan yang
     konkret: sebut blok dan penekanan atau bentuk yang seharusnya. Untuk teks
     karangan, minta batasan eksplisit yang melarang elemen itu.

# BATAS
Putaran perbaikan dibatasi {MAKS_PUTARAN} kali. Halaman yang tertahan tidak
menolong siapa pun — tahan hanya bila ada yang benar-benar keliru atau menyesatkan.

Kamu tidak pernah menyebut angka. Kalau ada nilai yang janggal, katakan "blok X
membawa nilai yang tidak berasal dari temuan", bukan nilainya berapa.

Kamu juga tidak menilai kecantikan. Yang kamu jaga adalah kesetiaan, titik fokus,
dan keterbacaan.

# BAHASA
Bahasa Indonesia, ringkas, spesifik. Sebut blok dengan pengenalnya.
""",
)


# Rantai penerbitan berpenilaian. Reporter menerbitkan, penilai memeriksa;
# `selesai` yang menghentikan lebih awal lewat escalate.
reporter_terjaga = LoopAgent(
    name="reporter_terjaga",
    description=(
        "Menerbitkan dokumen investigasi lalu memeriksanya sendiri, "
        f"paling banyak {MAKS_PUTARAN} putaran perbaikan."
    ),
    sub_agents=[reporter_agent, penilai_agent],
    max_iterations=MAKS_PUTARAN,
)


# Rantai penyajian visual, pola yang sama persis. Designer menerbitkan, penilai
# visual memeriksa. Dijalankan setelah reporter karena pemilihan blok miliknya.
designer_terjaga = LoopAgent(
    name="designer_terjaga",
    description=(
        "Menerbitkan infografis satu halaman lalu memeriksanya sendiri, "
        f"paling banyak {MAKS_PUTARAN} putaran perbaikan."
    ),
    sub_agents=[designer_agent, penilai_visual_agent],
    max_iterations=MAKS_PUTARAN,
)


# Rangkaian penuh dari satu temuan ke dua artefak. Urutannya bukan selera:
# `designer` membaca blok yang dipilih `reporter` dari state, jadi reporter harus
# selesai lebih dulu. Menjalankannya paralel akan membuat designer menebak.
#
# Kegagalan pada satu tahap tidak menghentikan tahap berikutnya — dokumen yang
# terbit tanpa infografis tetap berguna, dan sebaliknya. Yang tidak boleh terjadi
# adalah keduanya gagal diam-diam; itulah sebabnya tiap tool melaporkan
# kegagalannya apa adanya alih-alih mengembalikan hasil separuh jadi.
penerbitan_lengkap = SequentialAgent(
    name="penerbitan_lengkap",
    description=(
        "Menerbitkan dokumen investigasi lalu infografis satu halaman dari "
        "temuan yang sama, masing-masing dengan pemeriksaan mutunya sendiri."
    ),
    sub_agents=[reporter_terjaga, designer_terjaga],
)
