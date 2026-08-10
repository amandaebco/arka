"""Jalur emas — tulang punggung demo, disusun sebagai sasaran eksplisit.

Volume latar boleh acak; bagian ini **tidak boleh**. Kalau Babak 1 demo gagal,
penyebabnya jangan sampai keacakan yang apes. Setiap syarat di CLAUDE.md
diwujudkan di sini sebagai konstanta yang bisa dibaca dan diperiksa:

* armada seragam — satu model filler di lima pabrik
* pola berulang — kasus lama tuntas dengan solusi tercatat, kasus baru menguat
* rantai kausal penuh — Symptom → Cause → Damage → Part di kasus lama
* dokumen bisa dikutip — laporan inspeksi yang memuat solusi berhasil
* kasus ambigu — dua kandidat berselisih di bawah ambang eskalasi
* rantai pasok — sparepart vendor tunggal, lead time panjang, `static_criticality` rendah

Seluruh id turun dari seed lewat `uuid5`, jadi dataset dapat dibangun ulang
identik. Demo yang berperilaku sama tiap kali dijalankan itu syarat, bukan
kemewahan.

Domain sepenuhnya fiktif. Tidak ada nama perusahaan, sektor nyata, atau lokasi
asli — lihat Batasan Mutlak di CLAUDE.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

RUANG_NAMA = uuid.UUID("f62b9b7c-40f2-4e67-a3d7-f693484389e5")
SEED_BAWAAN = 20260806

# Titik acuan waktu dataset. Ditetapkan, bukan `now()`, supaya dataset yang
# dibangun ulang bulan depan tetap menghasilkan angka kebaruan yang sama.
SEKARANG = datetime(2026, 8, 1, tzinfo=UTC)


def id_stabil(seed: int, kunci: str) -> uuid.UUID:
    """UUID deterministik dari seed dan kunci semantik."""
    return uuid.uuid5(RUANG_NAMA, f"{seed}:{kunci}")


# ---------------------------------------------------------------------------
# Armada seragam
# ---------------------------------------------------------------------------

MODEL_FILLER = "Filler Rotary RF-8000"
TIPE_EQUIPMENT = "filler"

# Lima pabrik memakai model yang sama. Batas bawah dari CLAUDE.md: dengan dua
# pabrik saja, "penemuan" ARKA cuma perbandingan sepasang — tidak mengesankan.
PABRIK_ARMADA: tuple[tuple[str, str], ...] = (
    ("PLT-U", "Pabrik Utara"),
    ("PLT-S", "Pabrik Selatan"),
    ("PLT-B", "Pabrik Barat"),
    ("PLT-T", "Pabrik Timur"),
    ("PLT-G", "Pabrik Tengah"),
)

# Skema tag dirancang sendiri: <kode pabrik>/<tipe><nomor>. Sengaja tidak
# meniru format sistem manapun.
def tag_equipment(kode_pabrik: str, nomor: int) -> str:
    return f"{kode_pabrik}/FIL-{nomor:03d}"


# ---------------------------------------------------------------------------
# Kosakata kegagalan
# ---------------------------------------------------------------------------

GEJALA: tuple[tuple[str, str], ...] = (
    ("GJL-BOCOR-KEPALA", "Kebocoran produk di kepala pengisi"),
    ("GJL-AKURASI-TURUN", "Penurunan akurasi volume pengisian"),
    ("GJL-GETAR-NAIK", "Getaran meningkat pada putaran nominal"),
    ("GJL-SUARA-KASAR", "Suara kasar saat transisi katup"),
    ("GJL-BUSA-BERLEBIH", "Busa berlebih pada pengisian botol"),
)

PENYEBAB: tuple[tuple[str, str, str], ...] = (
    (
        "PNY-SEAL-DEGRADASI",
        "Degradasi seal kepala pengisi akibat batch material di bawah spesifikasi",
        "material",
    ),
    (
        "PNY-TORSI-MENYIMPANG",
        "Penyimpangan torsi kepala pengisi pasca perawatan terjadwal",
        "prosedur",
    ),
    (
        "PNY-POROS-TAK-SEJAJAR",
        "Ketidaksejajaran poros akibat pemasangan bearing",
        "pemasangan",
    ),
)

MODE_KEGAGALAN: tuple[tuple[str, str], ...] = (
    ("MOD-BOCOR-STATIS", "Kebocoran pada sambungan statis"),
    ("MOD-AUS-DINI", "Keausan dini komponen elastomer"),
)

KOMPONEN_FILLER: tuple[tuple[str, str], ...] = (
    ("SEAL", "Seal kepala pengisi"),
    ("KATUP", "Katup pengisi"),
    ("BRG", "Bearing poros putar"),
    ("NOZEL", "Nozel pengisi"),
)


# ---------------------------------------------------------------------------
# Sparepart — pembeda ARKA ada di sini
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpesifikasiSparepart:
    part_number: str
    nama: str
    vendor: str
    jumlah_vendor: int
    lead_time_minggu: int
    static_criticality: Decimal
    dipakai_di_pabrik: tuple[str, ...]


# Seal inilah inti Babak 2: dipakai lima pabrik, vendor tunggal, lead time enam
# minggu — tetapi master data menandainya rendah. Selisih terhadap kekritisan
# dinamis ARKA itulah nilai jualnya.
SEAL_KRITIS = SpesifikasiSparepart(
    part_number="SP-SEAL-8801",
    nama="Seal kepala pengisi RF-8000",
    vendor="Vendor Tunggal A",
    jumlah_vendor=1,
    lead_time_minggu=6,
    static_criticality=Decimal("0.30"),
    dipakai_di_pabrik=tuple(kode for kode, _ in PABRIK_ARMADA),
)

# Pembanding: barang serupa yang memang tidak kritis. Tanpa ini, "kekritisan
# dinamis" tidak punya lawan dan angka apa pun terlihat mengesankan.
SPAREPART_LAIN: tuple[SpesifikasiSparepart, ...] = (
    SpesifikasiSparepart(
        part_number="SP-NOZEL-2210",
        nama="Nozel pengisi RF-8000",
        vendor="Vendor B",
        jumlah_vendor=4,
        lead_time_minggu=1,
        static_criticality=Decimal("0.55"),
        dipakai_di_pabrik=tuple(kode for kode, _ in PABRIK_ARMADA),
    ),
    SpesifikasiSparepart(
        part_number="SP-BRG-4470",
        nama="Bearing poros putar RF-8000",
        vendor="Vendor C",
        jumlah_vendor=3,
        lead_time_minggu=2,
        static_criticality=Decimal("0.60"),
        dipakai_di_pabrik=("PLT-U", "PLT-S", "PLT-B"),
    ),
)


# ---------------------------------------------------------------------------
# Kasus — preseden lama dan kasus hidup
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KasusJalurEmas:
    """Satu kegagalan yang disusun sengaja, bukan hasil undian."""

    kunci: str
    kode_pabrik: str
    nomor_equipment: int
    mulai: datetime
    gejala: tuple[str, ...]
    penyebab: str | None
    komponen: str
    tuntas: bool
    solusi: str | None = None
    menit_henti: int = 0
    dokumen: str | None = None
    catatan: str = ""
    sparepart: tuple[str, ...] = field(default_factory=tuple)


def _hari(n: int) -> timedelta:
    return timedelta(days=n)


# Preseden: sudah selesai, penyebab terverifikasi, solusi tercatat, ada dokumen
# yang bisa dikutip. Tiga pabrik berbeda — inilah yang membuat ARKA bisa bilang
# "ini pernah terjadi di tempat lain dan sudah dibayar".
PRESEDEN: tuple[KasusJalurEmas, ...] = (
    KasusJalurEmas(
        kunci="preseden-barat",
        kode_pabrik="PLT-B",
        nomor_equipment=204,
        mulai=SEKARANG - _hari(430),
        # Ada gejala yang tidak muncul di kasus hidup (busa berlebih) — inilah
        # yang membuat irisannya di bawah satu dan skornya bisa membedakan.
        gejala=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN", "GJL-BUSA-BERLEBIH"),
        penyebab="PNY-SEAL-DEGRADASI",
        komponen="SEAL",
        tuntas=True,
        solusi=(
            "Penggantian seal satu set penuh dan pengetatan spesifikasi material "
            "pada pesanan berikutnya. Tidak berulang sejak penggantian."
        ),
        menit_henti=380,
        dokumen="DOC-INS-2024-0417",
        catatan="Batch seal dari kiriman yang sama terpasang di beberapa pabrik.",
        sparepart=("SP-SEAL-8801",),
    ),
    KasusJalurEmas(
        kunci="preseden-selatan",
        kode_pabrik="PLT-S",
        nomor_equipment=118,
        mulai=SEKARANG - _hari(320),
        gejala=("GJL-AKURASI-TURUN", "GJL-GETAR-NAIK"),
        penyebab="PNY-TORSI-MENYIMPANG",
        komponen="KATUP",
        tuntas=True,
        solusi="Penyetelan ulang torsi tanpa penggantian seal; tuntas.",
        menit_henti=145,
        dokumen="DOC-FME-2023-0091",
        catatan="Terjadi tak lama setelah perawatan terjadwal.",
    ),
    # Preseden torsi ketiga. Ditambahkan setelah skor diukur, bukan ditebak:
    # dengan dua preseden saja kandidat torsi tertinggal 0,09 dari kandidat seal,
    # sehingga Scout melaporkan tanpa ragu dan momen eskalasi tidak pernah terjadi.
    # Yang disetel adalah datanya — bobot dan ambang tetap, karena keduanya
    # kebijakan yang diterbitkan di CLAUDE.md dan Constitution.
    KasusJalurEmas(
        kunci="preseden-barat-torsi",
        kode_pabrik="PLT-B",
        nomor_equipment=204,
        mulai=SEKARANG - _hari(200),
        gejala=("GJL-AKURASI-TURUN", "GJL-GETAR-NAIK"),
        penyebab="PNY-TORSI-MENYIMPANG",
        komponen="KATUP",
        tuntas=True,
        solusi="Penyetelan ulang torsi kepala pengisi; akurasi pulih tanpa penggantian.",
        menit_henti=130,
        dokumen="DOC-FME-2023-0091",
        catatan="Pola torsi yang sama terlihat pada pabrik ketiga.",
    ),
    # Preseden torsi kedua. Tanpa ini kandidat torsi tidak punya koroborasi dan
    # skornya jatuh terlalu jauh di bawah kandidat seal — eskalasi tidak pernah
    # terpicu, dan Babak 1 demo kehilangan momen paling menariknya.
    KasusJalurEmas(
        kunci="preseden-tengah-torsi",
        kode_pabrik="PLT-G",
        nomor_equipment=412,
        mulai=SEKARANG - _hari(95),
        gejala=("GJL-AKURASI-TURUN", "GJL-GETAR-NAIK"),
        penyebab="PNY-TORSI-MENYIMPANG",
        komponen="KATUP",
        tuntas=True,
        solusi="Penyetelan ulang torsi setelah perawatan; akurasi pulih.",
        menit_henti=110,
        dokumen="DOC-STD-2024-0002",
        catatan="Pola yang sama terulang pasca perawatan terjadwal di pabrik lain.",
    ),
    KasusJalurEmas(
        kunci="preseden-timur",
        kode_pabrik="PLT-T",
        nomor_equipment=331,
        mulai=SEKARANG - _hari(150),
        gejala=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN", "GJL-GETAR-NAIK"),
        penyebab="PNY-SEAL-DEGRADASI",
        komponen="SEAL",
        tuntas=True,
        solusi="Penggantian seal; menunggu enam minggu karena pasokan vendor tunggal.",
        menit_henti=2_640,
        dokumen="DOC-WON-2025-1182",
        catatan="Henti panjang bukan karena perbaikannya, melainkan menunggu barang.",
        sparepart=("SP-SEAL-8801",),
    ),
)

# Kasus hidup: gejalanya beririsan kuat dengan preseden seal, tetapi juga cocok
# sebagian dengan preseden torsi. Selisih skor keduanya dirancang jatuh di bawah
# ambang 0,05 sehingga Scout wajib mengeskalasi, bukan menebak.
KASUS_HIDUP = KasusJalurEmas(
    kunci="kasus-hidup-utara",
    kode_pabrik="PLT-U",
    nomor_equipment=207,
    mulai=SEKARANG - _hari(3),
    gejala=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN", "GJL-GETAR-NAIK"),
    penyebab=None,  # belum diverifikasi — justru itu yang diselidiki
    komponen="SEAL",
    tuntas=False,
    menit_henti=0,
    catatan="Operator melaporkan rembesan di kepala pengisi menjelang akhir sif.",
)

# Kasus penguat: kejadian kedua pada armada yang sama, dekat waktunya. Inilah
# yang menaikkan komponen `corroboration` di atas ambang.
KASUS_PENGUAT = KasusJalurEmas(
    kunci="penguat-tengah",
    kode_pabrik="PLT-G",
    nomor_equipment=412,
    mulai=SEKARANG - _hari(21),
    gejala=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN"),
    penyebab=None,
    komponen="SEAL",
    tuntas=False,
    menit_henti=95,
    catatan="Gejala serupa muncul pada armada yang sama di pabrik lain.",
)

# Kasus yang memang harus diabaikan. Gejalanya tidak beririsan dengan preseden
# manapun dan komponennya di subsistem lain, sehingga skornya jatuh di bawah
# ambang pengabaian.
#
# Ada supaya penyaring Scout bisa dibantah. Sistem yang selalu menemukan sesuatu
# tidak membuktikan apa pun tentang kemampuannya memilih; yang meyakinkan justru
# ARKA yang menahan diri dan bisa menjelaskan alasannya.
KASUS_DIABAIKAN = KasusJalurEmas(
    kunci="kasus-sepele-selatan",
    kode_pabrik="PLT-S",
    nomor_equipment=118,
    mulai=SEKARANG - _hari(9),
    gejala=("GJL-SUARA-KASAR",),
    penyebab=None,
    komponen="BRG",
    tuntas=False,
    menit_henti=0,
    catatan="Suara kasar sesaat pada transisi katup; hilang setelah penyetelan rutin.",
)

SEMUA_KASUS: tuple[KasusJalurEmas, ...] = (
    *PRESEDEN,
    KASUS_PENGUAT,
    KASUS_HIDUP,
    KASUS_DIABAIKAN,
)


# ---------------------------------------------------------------------------
# Dokumen yang bisa dikutip
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DokumenInspeksi:
    canonical_id: str
    judul: str
    tanggal: date
    kode_pabrik: str
    isi: str


DOKUMEN: tuple[DokumenInspeksi, ...] = (
    DokumenInspeksi(
        canonical_id="DOC-INS-2024-0417",
        judul="Laporan Inspeksi Kepala Pengisi — Pabrik Barat",
        tanggal=(SEKARANG - _hari(425)).date(),
        kode_pabrik="PLT-B",
        isi=(
            "Pemeriksaan kepala pengisi menemukan seal mengeras dan kehilangan "
            "elastisitas jauh sebelum umur pakai nominal. Uji material pada "
            "potongan seal menunjukkan komposisi elastomer di bawah spesifikasi "
            "pesanan. Seluruh seal pada mesin diganti satu set. Setelah "
            "penggantian, kebocoran tidak berulang dan akurasi volume kembali "
            "ke rentang normal. Direkomendasikan pengetatan spesifikasi material "
            "pada pesanan berikutnya dan pemeriksaan batch yang sama di pabrik lain."
        ),
    ),
    DokumenInspeksi(
        canonical_id="DOC-FME-2023-0091",
        judul="Catatan Analisis Mode Kegagalan — Kepala Pengisi",
        tanggal=(SEKARANG - _hari(315)).date(),
        kode_pabrik="PLT-S",
        isi=(
            "Penurunan akurasi volume tanpa disertai kebocoran umumnya menunjuk "
            "pada penyimpangan torsi kepala pengisi, bukan degradasi seal. "
            "Pembeda utamanya adalah ada tidaknya rembesan pada sambungan statis. "
            "Penyetelan ulang torsi memulihkan akurasi tanpa penggantian komponen."
        ),
    ),
    DokumenInspeksi(
        canonical_id="DOC-WON-2025-1182",
        judul="Laporan Penyelesaian Pekerjaan — Penggantian Seal Pabrik Timur",
        tanggal=(SEKARANG - _hari(120)).date(),
        kode_pabrik="PLT-T",
        isi=(
            "Penggantian seal kepala pengisi tuntas dan mesin kembali beroperasi "
            "normal. Perbaikan sendiri selesai dalam satu sif; sebagian besar "
            "waktu henti habis menunggu kedatangan seal dari vendor tunggal. "
            "Tidak tersedia pemasok alternatif yang memenuhi spesifikasi. "
            "Direkomendasikan meninjau ulang penggolongan kekritisan material ini "
            "karena penggolongan saat ini tidak mencerminkan risiko pasokannya."
        ),
    ),
    DokumenInspeksi(
        canonical_id="DOC-STD-2024-0002",
        judul="Standar Perawatan Berkala Filler Rotary RF-8000",
        tanggal=(SEKARANG - _hari(500)).date(),
        kode_pabrik="PLT-U",
        isi=(
            "Perawatan berkala kepala pengisi mencakup pemeriksaan seal, "
            "pengukuran torsi, dan uji akurasi volume. Penyimpangan torsi pasca "
            "perawatan harus diperiksa ulang sebelum mesin dilepas ke produksi."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Syarat yang harus dipenuhi — dipakai `validation.py` sebagai penjaga
# ---------------------------------------------------------------------------

JUMLAH_PABRIK_ARMADA_MINIMAL = 5
JUMLAH_DOKUMEN_MINIMAL = 3
AMBANG_ESKALASI = Decimal("0.05")
LEAD_TIME_KRITIS_MINGGU = 6
