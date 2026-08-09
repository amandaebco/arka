"""Uji jalur deploy ke Vertex AI Agent Engine dengan agent paling sederhana.

Sengaja memakai `app/agents/hello.py` — nol dependensi ARKA, tanpa DB, tanpa
reporting. Kalau deploy gagal, penyebabnya pasti jalur deploy-nya sendiri dan
bukan kode domain. Itulah gunanya asap sebelum api.

    uv run python scripts/deploy_hello.py            # deploy lalu panggil
    uv run python scripts/deploy_hello.py --hapus    # bersihkan resource
"""

import argparse

import vertexai
from vertexai import agent_engines

from app.agents.hello import root_agent

PROJECT = "ebco-aihack-amanda"
# Agent Engine berjalan di region, bukan `global`. Model `gemini-3.6-flash`
# sendiri hanya tersedia di `global` — apakah agent di region bisa memanggilnya
# adalah salah satu hal yang diuji di sini.
LOCATION = "us-central1"
BUCKET = "gs://ebco-aihack-amanda-arka-staging"
NAMA = "arka-hello"
NAMA_PDF = "arka-uji-pdf"


def klien() -> vertexai.Client:
    return vertexai.Client(project=PROJECT, location=LOCATION)


def deploy_uji_pdf() -> str:
    """Deploy agent uji PDF — menjawab apakah Chromium bisa hidup di sana."""
    from app.agents.uji_pdf import root_agent as agen_pdf

    c = klien()
    print("Membangun dengan Chromium — jauh lebih lama dari hello…")
    hasil = c.agent_engines.create(
        agent=agent_engines.AdkApp(agent=agen_pdf),
        config={
            "display_name": NAMA_PDF,
            "description": "Uji render PDF di Agent Engine",
            "staging_bucket": BUCKET,
            "extra_packages": ["app", "installation_scripts/install_chromium.sh"],
            "requirements": [
                "google-cloud-aiplatform[adk,agent-engines]",
                "cloudpickle",
                "pydantic",
                "pydantic-settings",
                "python-dotenv",
                "jinja2",
                "playwright",
            ],
            "env_vars": {
                "GOOGLE_CLOUD_LOCATION": "global",
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                # Harus sama dengan yang dipakai skrip pemasangan.
                "PLAYWRIGHT_BROWSERS_PATH": "/opt/ms-playwright",
            },
            "build_options": {
                "installation_scripts": ["installation_scripts/install_chromium.sh"]
            },
        },
    )
    nama = hasil.api_resource.name
    print("RESOURCE:", nama)
    return nama


def deploy() -> str:
    c = klien()
    aplikasi = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)
    print("Membangun dan mengunggah — biasanya beberapa menit…")
    hasil = c.agent_engines.create(
        agent=aplikasi,
        config={
            "display_name": NAMA,
            "description": "Uji jalur deploy ARKA",
            "staging_bucket": BUCKET,
            # Agent dikirim dalam bentuk pickle, jadi paket `app` harus ikut
            # diunggah — tanpa ini container gagal start dengan
            # ModuleNotFoundError saat memuat ulang objeknya.
            "extra_packages": ["app"],
            "requirements": [
                "google-cloud-aiplatform[adk,agent-engines]",
                "cloudpickle",
                "pydantic",
                "pydantic-settings",
                "python-dotenv",
            ],
            "env_vars": {
                "GOOGLE_CLOUD_LOCATION": "global",
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
            },
        },
    )
    nama = hasil.api_resource.name
    print("RESOURCE:", nama)
    return nama


def panggil(nama: str, pesan: str = "Halo, nama saya Amanda.") -> None:
    """Buktikan agent benar-benar menjawab, bukan sekadar berhasil terunggah."""
    c = klien()
    jauh = c.agent_engines.get(name=nama)
    sesi = jauh.create_session(user_id="uji")
    for peristiwa in jauh.stream_query(
        user_id="uji", session_id=sesi["id"], message=pesan
    ):
        for bagian in peristiwa.get("content", {}).get("parts", []):
            if bagian.get("text"):
                print("[jauh]", bagian["text"].strip())
            if bagian.get("function_call"):
                print("[tool]", bagian["function_call"]["name"])


def hapus() -> None:
    c = klien()
    for a in c.agent_engines.list():
        if a.api_resource.display_name in (NAMA, NAMA_PDF):
            print("Menghapus", a.api_resource.name)
            c.agent_engines.delete(name=a.api_resource.name, force=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hapus", action="store_true", help="Hapus agent uji")
    parser.add_argument("--nama", help="Panggil resource yang sudah ada")
    parser.add_argument("--pdf", action="store_true", help="Deploy agent uji render PDF")
    argumen = parser.parse_args()

    if argumen.hapus:
        hapus()
        return
    if argumen.pdf:
        panggil(argumen.nama or deploy_uji_pdf(), "Tolong uji render PDF sekarang.")
        return
    panggil(argumen.nama or deploy())


if __name__ == "__main__":
    main()
