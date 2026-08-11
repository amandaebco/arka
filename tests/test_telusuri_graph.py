"""Tool traversal untuk agent tanya-jawab.

Yang diuji bukan angkanya — itu milik BigQuery — melainkan pembagian keputusan.
Model memilih **dari mana berjalan dan sejauh apa**; ia tidak pernah memilih apa
yang dikatakan jalurnya. Kalau batas itu kabur, klaim "agent menelusuri graph"
berubah diam-diam menjadi "model mengarang rute".
"""

from __future__ import annotations

import app.agents.tanya_jawab as tj
from app.bigquery.traversal import MAX_HOPS, Path


class Ctx:
    """Pengganti minimal ToolContext: tool ini hanya butuh state."""

    def __init__(self):
        self.state: dict = {}


def _jalur(hops: int = 2, target: str = "Plant", nama: str = "Pabrik Barat") -> Path:
    return Path(
        target_id="x",
        target_label=target,
        target_name=nama,
        hops=hops,
        edge_labels=("DIPASOK_OLEH⁻¹", "MEMILIKI_KOMPONEN⁻¹")[:hops],
        node_names=("SP-SEAL-8801", "seal", nama)[: hops + 1],
    )


def _pasang(monkeypatch, hasil, tangkap=None):
    def palsu(label, nama, *, max_hops, only_label):
        if tangkap is not None:
            tangkap.update(label=label, nama=nama, max_hops=max_hops, only_label=only_label)
        return hasil

    monkeypatch.setattr("app.bigquery.traversal.traverse", palsu)


class TestKedalamanDijepit:
    async def test_kedalaman_di_atas_batas_dipangkas(self, monkeypatch):
        """Model boleh salah minta; ia tidak boleh bisa memaksa kueri raksasa."""
        tangkap: dict = {}
        _pasang(monkeypatch, [_jalur()], tangkap)
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 99, "", Ctx())
        assert tangkap["max_hops"] == MAX_HOPS

    async def test_kedalaman_nol_dinaikkan_ke_satu(self, monkeypatch):
        tangkap: dict = {}
        _pasang(monkeypatch, [_jalur()], tangkap)
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 0, "", Ctx())
        assert tangkap["max_hops"] == 1

    async def test_kedalaman_wajar_diteruskan_apa_adanya(self, monkeypatch):
        tangkap: dict = {}
        _pasang(monkeypatch, [_jalur()], tangkap)
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 4, "Plant", Ctx())
        assert tangkap["max_hops"] == 4
        assert tangkap["only_label"] == "Plant"

    async def test_sampai_label_kosong_berarti_semua(self, monkeypatch):
        tangkap: dict = {}
        _pasang(monkeypatch, [_jalur()], tangkap)
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 2, "", Ctx())
        assert tangkap["only_label"] is None


class TestJalurDikembalikanUtuh:
    async def test_setiap_hop_disebut(self, monkeypatch):
        """Jalur yang diringkas kehilangan justru bagian yang bisa diperiksa."""
        _pasang(monkeypatch, [_jalur()])
        hasil = await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 2, "", Ctx())
        assert "SP-SEAL-8801" in hasil
        assert "-[DIPASOK_OLEH⁻¹]->" in hasil
        assert "Pabrik Barat" in hasil

    async def test_jalur_disimpan_ke_state_untuk_answerer(self, monkeypatch):
        _pasang(monkeypatch, [_jalur()])
        ctx = Ctx()
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 2, "", ctx)
        simpan = ctx.state[tj.KUNCI_JALUR]
        assert simpan["mulai"] == "SparePart SP-SEAL-8801"
        assert simpan["jumlah"] == 1
        assert simpan["jalur"]


class TestJumlahDibatasi:
    async def test_hanya_sebagian_yang_masuk_prompt(self, monkeypatch):
        """Lima hop bisa menghasilkan ribuan jalur; yang tak terbaca tak berguna."""
        banyak = [_jalur(nama=f"Pabrik {n}") for n in range(50)]
        _pasang(monkeypatch, banyak)
        ctx = Ctx()
        hasil = await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 5, "", ctx)
        assert len(ctx.state[tj.KUNCI_JALUR]["jalur"]) == tj.MAKS_JALUR
        assert "50 jalur" in hasil, "jumlah sebenarnya harus tetap dilaporkan"

    async def test_yang_terdekat_didahulukan(self, monkeypatch):
        """Jalur pendek menjelaskan lebih banyak per langkahnya."""
        _pasang(monkeypatch, [_jalur(hops=2), _jalur(hops=1, nama="seal")])
        ctx = Ctx()
        await tj.telusuri_graph("SparePart", "SP-SEAL-8801", 5, "", ctx)
        assert "seal" in ctx.state[tj.KUNCI_JALUR]["jalur"][0]


class TestKosongDikatakanApaAdanya:
    async def test_node_tak_dikenal_tidak_dibungkus_jawaban(self, monkeypatch):
        """Nama yang salah harus terlihat sebagai nama yang salah."""
        _pasang(monkeypatch, [])
        hasil = await tj.telusuri_graph("SparePart", "SP-TIDAK-ADA", 3, "", Ctx())
        assert "Tidak ada" in hasil
        assert "Periksa penamaannya" in hasil

    async def test_hasil_kosong_tidak_menulis_state(self, monkeypatch):
        _pasang(monkeypatch, [])
        ctx = Ctx()
        await tj.telusuri_graph("SparePart", "SP-TIDAK-ADA", 3, "", ctx)
        assert tj.KUNCI_JALUR not in ctx.state


class TestTerpasangPadaAgent:
    def test_retriever_punya_ketiga_tool(self):
        nama = {getattr(t, "__name__", getattr(t, "name", "")) for t in tj.retriever_agent.tools}
        assert {"cari_konteks", "perluas_pencarian", "telusuri_graph"} <= nama

    def test_answerer_membaca_jalur_dari_state(self):
        assert "{jalur_traversal?}" in tj.answerer_agent.instruction

    def test_answerer_diminta_mengutip_jalurnya(self):
        instruksi = tj.answerer_agent.instruction.lower()
        assert "path" in instruksi
        assert "⁻¹" in tj.answerer_agent.instruction
