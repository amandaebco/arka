"""Agent hello-world — dipakai untuk memverifikasi jalur deploy ke Agent Engine.

Sengaja tanpa dependensi ARKA (DB, graph, reporting) supaya kegagalan deploy
pasti berasal dari jalur deploy-nya, bukan dari kode domain.
"""

from google.adk.agents import Agent


def salam(nama: str) -> dict:
    """Mengembalikan salam untuk nama yang diberikan.

    Args:
        nama: Nama orang yang disapa.
    """
    return {"status": "ok", "pesan": f"Halo {nama}, ARKA aktif."}


root_agent = Agent(
    name="arka_hello",
    model="gemini-2.5-flash",
    description="Agent uji coba jalur deploy ARKA.",
    instruction=(
        "Kamu adalah agent uji coba ARKA. Jawab singkat dalam bahasa Indonesia. "
        "Kalau pengguna menyebut sebuah nama, panggil tool `salam`."
    ),
    tools=[salam],
)
