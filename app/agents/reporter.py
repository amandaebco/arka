"""Agent `reporter` — memutuskan blok mana yang masuk dokumen dan urutannya.

Serah-terima masuk adalah objek `Finding` di kunci state `finding`. Selama
kontrak itu dipenuhi, reporter tidak peduli asalnya:

* **Sekarang** — `muat_temuan` mengisinya dari JSON di dalam prompt.
* **Nanti** — investigator menulis ke kunci state yang sama, dan `muat_temuan`
  tidak lagi dipanggil. Tidak ada baris di modul ini yang perlu berubah.

Batas yang dijaga modul ini: model memilih blok, urutan, dan menulis narasi.
Seluruh angka, skor, dan sitasi dirender deterministik oleh `app.reporting`.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.core.config import get_settings
from app.reporting.blocks import URUTAN_BAKU, susun_blok
from app.reporting.cloud_storage import unggah_dashboard_ke_cloud_storage
from app.reporting.dokumen import JENIS, KonteksDokumen, ambil_jenis
from app.reporting.finding import Finding
from app.reporting.memo import render_dokumen_html, render_dokumen_pdf
from app.reporting.narasi import bersihkan_peta_narasi

logger = logging.getLogger(__name__)

# Kunci serah-terima investigator → reporter.
KUNCI_TEMUAN = "finding"


def _muat_peta(mentah: str | None, label: str) -> dict:
    """Baca argumen JSON berbentuk peta. Isi yang tidak sah tidak menggagalkan terbit."""
    if not mentah:
        return {}
    try:
        nilai = json.loads(mentah)
    except json.JSONDecodeError as exc:
        logger.warning("Argumen %s bukan JSON yang sah (%s) — diabaikan", label, exc)
        return {}
    return nilai if isinstance(nilai, dict) else {}


def _ambil_temuan(tool_context: ToolContext) -> Finding | None:
    mentah = tool_context.state.get(KUNCI_TEMUAN)
    if not mentah:
        return None
    if isinstance(mentah, Finding):
        return mentah
    try:
        return Finding.model_validate(
            json.loads(mentah) if isinstance(mentah, str) else mentah
        )
    except Exception as exc:  # noqa: BLE001 — dilaporkan ke model, bukan dilempar
        logger.warning("Temuan di state tidak dapat dibaca: %s", exc)
        return None


def muat_temuan(finding_json: str, tool_context: ToolContext) -> str:
    """Memuat satu temuan investigasi dari JSON ke dalam sesi.

    Jalur masukan sementara selama investigator belum tersambung. Setelah
    tersambung, temuan sudah ada di sesi dan alat ini tidak perlu dipanggil.

    Args:
        finding_json: Objek Finding dalam bentuk JSON.
        tool_context: Disuntikkan ADK.

    Returns:
        Ringkasan temuan dan daftar blok yang punya data.
    """
    try:
        finding = Finding.model_validate_json(finding_json)
    except Exception as exc:  # noqa: BLE001
        return f"JSON temuan tidak valid: {exc}"

    tool_context.state[KUNCI_TEMUAN] = finding.model_dump(mode="json")
    logger.info("Temuan %s dimuat untuk %s", finding.finding_id, finding.equipment_tag)
    return ringkas_temuan(tool_context)


def ringkas_temuan(tool_context: ToolContext) -> str:
    """Menjelaskan isi temuan saat ini dan blok mana yang punya data.

    Panggil sebelum menyusun memo agar pilihan blok tidak menebak-nebak.

    Args:
        tool_context: Disuntikkan ADK.

    Returns:
        Ringkasan temuan beserta ketersediaan tiap blok.
    """
    finding = _ambil_temuan(tool_context)
    if finding is None:
        return "Belum ada temuan di sesi ini. Muat temuan lebih dulu."

    blok = susun_blok(finding)
    tersedia = [b.id for b in blok.values() if b.tersedia]
    kosong = [b.id for b in blok.values() if not b.tersedia]

    baris = [
        f"Temuan {finding.finding_id} — {finding.equipment_tag} di {finding.pabrik}.",
        f"Keyakinan: {finding.keyakinan}. Eskalasi: {'ya' if finding.perlu_eskalasi else 'tidak'}.",
        f"Kandidat penyebab: {len(finding.kandidat)}. Preseden: {len(finding.preseden)}. "
        f"Sitasi: {len(finding.semua_sitasi())}.",
        f"Blok tersedia: {', '.join(tersedia)}.",
    ]
    if kosong:
        baris.append(f"Blok tanpa data (jangan dipilih): {', '.join(kosong)}.")
    return "\n".join(baris)


async def terbitkan_dokumen(
    jenis_dokumen: str,
    urutan_blok: list[str],
    narasi_json: str,
    konteks_json: str,
    tool_context: ToolContext,
) -> str:
    """Merender dokumen investigasi dan menyimpannya sebagai artifact sesi.

    Args:
        jenis_dokumen: "memo", "nota_dinas", atau "laporan". Nilai lain
            diperlakukan sebagai memo.
        urutan_blok: Id blok sesuai urutan yang dikehendaki. Kosongkan untuk
            memakai urutan bawaan jenis dokumen. Blok kosong disaring otomatis;
            `ringkasan` dan `sitasi` selalu disertakan.
        narasi_json: Peta JSON {id_blok: narasi}. Narasi bersifat kualitatif —
            jangan menuliskan angka, skor, atau tanggal di dalamnya.
        konteks_json: Peta JSON kelengkapan surat (nomor, kepada, dari,
            perihal, tembusan, penanda_tangan, jabatan_penanda_tangan,
            periode). Wajib untuk nota dinas, boleh kosong untuk memo.
        tool_context: Disuntikkan ADK.

    Returns:
        Nama berkas artifact yang tersimpan, atau penjelasan kegagalan.
    """
    finding = _ambil_temuan(tool_context)
    if finding is None:
        return "Belum ada temuan di sesi ini. Muat temuan lebih dulu."

    if not finding.semua_sitasi():
        logger.warning("Penerbitan %s ditolak: tanpa sitasi", finding.finding_id)
        return (
            "Dokumen tidak diterbitkan: temuan ini tidak memuat satu pun rujukan "
            "dokumen sumber. Setiap klaim harus dapat ditelusuri. Sampaikan hal ini "
            "kepada pengguna dan jangan mencoba menerbitkan ulang."
        )

    jenis = ambil_jenis(jenis_dokumen)
    narasi_mentah = _muat_peta(narasi_json, "narasi")
    narasi, narasi_ditolak = bersihkan_peta_narasi(narasi_mentah)
    try:
        konteks = KonteksDokumen.model_validate(_muat_peta(konteks_json, "konteks"))
    except Exception as exc:  # noqa: BLE001 — kelengkapan surat tidak boleh menggagalkan terbit
        logger.warning("Konteks dokumen tidak sah (%s) — dipakai konteks kosong", exc)
        konteks = KonteksDokumen()

    # Rekam pilihan yang dipakai supaya penilai memeriksa dokumen yang benar-benar
    # terbit, bukan menebak dari percakapan.
    tool_context.state["jenis_terakhir"] = jenis.id
    tool_context.state["urutan_terakhir"] = list(urutan_blok or jenis.urutan_bawaan)
    # Yang direkam narasi mentah, bukan yang sudah disaring — penilai perlu
    # melihat pelanggarannya untuk bisa menegur, bukan hasil bersihnya.
    tool_context.state["narasi_terakhir"] = narasi_mentah
    tool_context.state["konteks_terakhir"] = konteks.model_dump(mode="json")

    # Yang diserahkan ke manusia selalu PDF. HTML adalah bentuk kerja internal —
    # dipakai `scripts/render_contoh.py` saat menyetel template, tidak pernah
    # menjadi dokumen resmi. Karena itu kegagalan render tidak mundur diam-diam
    # ke HTML: dokumen setengah jadi yang terlihat resmi lebih berbahaya daripada
    if jenis.id == "dashboard":
        import os
        import re
        from datetime import datetime


        tag_bersih = re.sub(
            r"[^a-zA-Z0-9_-]", "_", finding.equipment_tag or finding.finding_id
        )
        waktu = datetime.now().strftime("%Y%m%d-%H%M%S")
        nama = f"dashboard-{tag_bersih}-{waktu}.html"

        bucket_name = os.getenv("GCS_BUCKET_NAME", "ebco-aihack-amanda-arka-staging")
        url_prediksi = f"https://storage.googleapis.com/{bucket_name}/dashboards/{nama}"

        konteks_obj = konteks if isinstance(konteks, KonteksDokumen) else KonteksDokumen()
        konteks_obj = konteks_obj.model_copy(update={"url_dashboard": url_prediksi})

        isi_html = render_dokumen_html(finding, jenis, urutan_blok, narasi, konteks_obj)



        try:
            await tool_context.save_artifact(
                filename=nama,
                artifact=types.Part.from_bytes(
                    data=isi_html.encode("utf-8"), mime_type="text/html"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Penyimpanan artifact dashboard gagal: %s", exc)
            return "Dashboard HTML berhasil dirender, tetapi gagal disimpan sebagai artifact."

        url_dashboard = await unggah_dashboard_ke_cloud_storage(nama, isi_html)
        logger.info("%s %s tersimpan -> %s", jenis.label, nama, url_dashboard)
        status_eskalasi = "⚠️ Perlu Eskalasi" if finding.perlu_eskalasi else "✅ Terverifikasi"

        pesan = (
            f"🖥️ **Executive Dashboard `{finding.equipment_tag}`** ({finding.pabrik} · {status_eskalasi})\n"
            f"🌐 [Buka Dashboard Interaktif di Peramban]({url_dashboard})"
        )
        return pesan


    dasar = f"{jenis.id}-{finding.finding_id}"
    try:
        isi = await render_dokumen_pdf(finding, jenis, urutan_blok, narasi, konteks)

    except Exception as exc:  # noqa: BLE001 — dilaporkan ke model, bukan dilempar
        logger.error("Render PDF gagal: %s", exc)
        return (
            "Dokumen gagal diterbitkan: mesin render PDF tidak tersedia "
            f"({type(exc).__name__}). Sampaikan kegagalan ini kepada pengguna apa "
            "adanya dan jangan mencoba menerbitkan ulang — masalahnya di "
            "lingkungan, bukan pada temuan atau pilihan blokmu."
        )

    try:
        await tool_context.save_artifact(
            filename=f"{dasar}.pdf",
            artifact=types.Part.from_bytes(data=isi, mime_type="application/pdf"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Penyimpanan artifact gagal: %s", exc)
        return "Dokumen berhasil dirender, tetapi gagal disimpan sebagai artifact."

    nama = f"{dasar}.pdf"

    logger.info("%s %s tersimpan (%d bita)", jenis.label, nama, len(isi))
    kandidat_teratas = (
        finding.kandidat[0].nama if finding.kandidat else "Tidak teridentifikasi"
    )
    status_eskalasi = (
        "⚠️ MEMERLUKAN ESKALASI MANAJEMEN"
        if finding.perlu_eskalasi
        else "✅ TERVERIFIKASI OTOMATIS"
    )
    summary_md = (
        f"\n\n### 📄 Ringkasan Dokumen ({jenis.label})\n"
        f"- **Aset / Tag**: {finding.pabrik} · `{finding.equipment_tag}`\n"
        f"- **Penyebab Utama**: {kandidat_teratas} (Keyakinan: {finding.keyakinan.upper()})\n"
        f"- **Status Eskalasi**: {status_eskalasi}\n"
        f"- **Sitasi Terlampir**: {len(finding.semua_sitasi())} dokumen terverifikasi\n"
    )
    pesan = f"{jenis.label} tersimpan sebagai {nama} ({len(isi):,} bita).{summary_md}"
    if narasi_ditolak:
        # Model diberi tahu agar tidak mengulanginya, bukan agar mencoba lagi.
        pesan += (
            "\n*Catatan: kalimat bermuatan angka pada narasi blok "
            f"{', '.join(narasi_ditolak)} dibuang otomatis — angka hanya berasal "
            "dari tabel. Jangan menerbitkan ulang; cukup hindari pada dokumen berikutnya.*"
        )

    return pesan



reporter_agent = LlmAgent(
    name="reporter",
    model=get_settings().vertex_ai_model,
    description=(
        "Menyusun dokumen investigasi dari temuan — memo, nota dinas, atau laporan: "
        "memilih jenis, blok, urutan, dan menulis narasi. "
        "Tidak pernah menghitung atau menyebut angka."
    ),
    tools=[muat_temuan, ringkas_temuan, terbitkan_dokumen],
    instruction=f"""
# PERAN
Kamu adalah Reporter pada ARKA, agent keandalan aset untuk manufaktur FMCG multi-pabrik.
Satu keputusan menjadi milikmu sepenuhnya: **blok mana yang masuk memo dan dalam urutan apa**.

# BATAS YANG TIDAK BOLEH DILANGGAR
1. **Dilarang menggunakan karakter em-dash ("—") atau double dash ("--")** dalam seluruh narasi, perihal, atau judul laporan. Gunakan koma, titik dua (:), atau tanda hubung biasa (-) jika diperlukan.
2. Kamu tidak pernah menyebutkan angka. Bukan skor, bukan tanggal, bukan jam downtime, bukan jumlah pabrik. Semua nilai itu dirender langsung dari knowledge graph ke dalam tabel memo. Menuliskannya ulang di narasi berisiko salah ketik, dan satu angka salah menghancurkan kredibilitas seluruh laporan.


Larangan ini mencakup angka yang ditulis sebagai kata. "dua kandidat" sama
terlarangnya dengan "2 kandidat".

Tulis "skornya jauh di atas kandidat lain", bukan "skornya 0,82".
Tulis "berulang di beberapa pabrik", bukan "berulang di 5 pabrik".
Tulis "beberapa kandidat bersaing ketat", bukan "dua kandidat bersaing ketat".

Kalimat narasi yang memuat angka dibuang otomatis sebelum masuk dokumen.
Kalau itu terjadi, dokumen tetap terbit dengan narasi yang lebih pendek —
jangan menerbitkan ulang, cukup jangan mengulanginya.

Kamu juga tidak menyimpulkan penyebab sendiri. Penyebab sudah diputuskan investigator;
tugasmu menyajikannya.

# MASUKAN PEMERIKSAAN
{{masukan_qa?}}

Bila bagian di atas berisi masukan, itu datang dari penilai mutu atas dokumen yang
**baru saja kamu terbitkan**. Kerjakan perbaikannya lalu terbitkan ulang — jangan
mengulang dokumen yang sama, dan jangan membantah. Bila bagian itu kosong, ini
penerbitan pertama; kerjakan seperti biasa.

# LANGKAH
1. Panggil `ringkas_temuan` lebih dulu. Jangan memilih blok sebelum tahu isinya.
   Bila belum ada temuan di sesi dan pengguna menyertakan JSON temuan, panggil `muat_temuan`.
2. Tentukan jenis dokumen — lihat bagian berikutnya.
3. Tentukan urutan blok. Blok yang tersedia:
   {", ".join(URUTAN_BAKU)}
   Jangan memilih blok yang dilaporkan kosong. Kosongkan urutan bila urutan
   bawaan jenis dokumen sudah tepat.
4. Tulis narasi pengantar untuk blok yang memerlukannya — satu sampai dua kalimat,
   menjelaskan makna, bukan mengulang isi tabel. Blok tabel murni boleh tanpa narasi.
5. Panggil `terbitkan_dokumen`.
6. Sampaikan hasilnya ke pengguna: apa isi dokumen dan mengapa urutannya begitu.

# JENIS DOKUMEN
Isi ketiganya sama — yang berbeda hanya bentuk dan derajat formalitas.

- `{JENIS["memo"].id}` — bawaan. Ringkas, untuk reliability engineer di lapangan.
  Pilih ini bila pengguna tidak menyebut bentuk tertentu. Keringkasan adalah
  tujuannya, bukan kekurangannya: memo harus muat satu halaman. Jangan
  memasukkan semua blok hanya karena datanya tersedia — bila urutan bawaan
  sudah memadai, kosongkan `urutan_blok`.
- `{JENIS["nota_dinas"].id}` — korespondensi resmi antar unit, menuntut tindak
  lanjut penerima. Butuh kelengkapan surat lewat `konteks_json`: minimal
  `kepada`, `dari`, dan `perihal`. Bila pengguna belum menyebutkannya,
  **tanyakan lebih dulu** — jangan mengarang nama, jabatan, atau nomor surat.
- `{JENIS["laporan"].id}` — rekap lengkap termasuk jejak penalaran, untuk
  pembaca yang ingin mengaudit cara ARKA sampai pada kesimpulan.
- `{JENIS["dashboard"].id}` — dashboard eksekutif interaktif web (Dark Glassmorphism).
  Pilih ini bila pengguna meminta dashboard, monitor eksekutif, atau tampilan web interaktif.



# PERTIMBANGAN URUTAN
- `ringkasan` selalu membuka, `sitasi` selalu menutup. Keduanya wajib dan otomatis.
- Bila temuan perlu eskalasi, dahulukan `kandidat_penyebab` — pembaca harus segera
  melihat dua kandidat yang bersaing ketat.
- Bila kekuatan temuan justru ada pada pengulangan lintas pabrik, dahulukan
  `preseden_lintas_pabrik` sebelum kandidat.
- `sparepart_kritis` naik ke atas hanya bila selisihnya terhadap master data
  memang menjadi inti temuan.
- `jejak_penalaran` menutup rangkaian sebelum sitasi — pembaca yang skeptis
  membacanya paling akhir.

# BAHASA
Bahasa Indonesia baku, ringkas, nada teknis dan tenang. Hindari kata sifat berlebihan.
Pembacamu adalah reliability engineer yang sibuk.
""",
)
