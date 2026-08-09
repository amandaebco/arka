"""Deploy berbasis kode sumber — alternatif jalur pickle.

Dipakai bila agent perlu dikirim sebagai sumber, bukan objek ter-pickle.
Dua syarat yang mahal ditemukan ulang: entrypoint wajib berupa `AdkApp`
(bukan agent mentah), dan `class_methods` wajib diisi sendiri.

Catatan penting: `build_options` beserta `installation_scripts` divalidasi
SDK lalu **tidak pernah dikirim ke API** — di jalur ini maupun jalur pickle.
Jangan mengandalkannya untuk memasang dependensi sistem.

    uv run python scripts/deploy_sumber.py
"""

import argparse
from pathlib import Path

import vertexai
from vertexai._genai import _agent_engines_utils as _u

PROJECT = "ebco-aihack-amanda"
LOCATION = "us-central1"
BUCKET = "gs://ebco-aihack-amanda-arka-staging"
NAMA = "arka-sumber"

AKAR = Path(__file__).resolve().parent.parent
BERKAS_REQUIREMENTS = AKAR / "requirements-agent.txt"

REQUIREMENTS = """google-cloud-aiplatform[adk,agent-engines]
cloudpickle
pydantic
pydantic-settings
python-dotenv
jinja2
playwright
"""


def siapkan() -> None:
    BERKAS_REQUIREMENTS.write_text(REQUIREMENTS, encoding="utf-8")


def deploy() -> str:
    siapkan()
    c = vertexai.Client(project=PROJECT, location=LOCATION)
    print("Mengunggah sumber dan membangun — ini lama…")
    # `class_methods` wajib pada jalur sumber. Bentuknya sama dengan yang
    # dihasilkan otomatis di jalur pickle, jadi dipinjam dari sana.
    from app.agents.aplikasi import aplikasi

    metode = [
        _u._to_dict(m)
        for m in _u._generate_class_methods_spec_or_raise(
            agent=aplikasi, operations=aplikasi.register_operations()
        )
    ]

    hasil = c.agent_engines.create(
        config={
            "class_methods": metode,
            "display_name": NAMA,
            "description": "Deploy ARKA lewat jalur kode sumber",
            "staging_bucket": BUCKET,
            "source_packages": [
                "app",
                "requirements-agent.txt",
            ],
            "requirements_file": "requirements-agent.txt",
            "entrypoint_module": "app.agents.aplikasi",
            "entrypoint_object": "aplikasi",
            "agent_framework": "google-adk",
            "env_vars": {
                "GOOGLE_CLOUD_LOCATION": "global",
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "PLAYWRIGHT_BROWSERS_PATH": "/opt/ms-playwright",
            },
        },
    )
    nama = hasil.api_resource.name
    print("RESOURCE:", nama)
    return nama


def panggil(nama: str) -> None:
    c = vertexai.Client(project=PROJECT, location=LOCATION)
    jauh = c.agent_engines.get(name=nama)
    sesi = jauh.create_session(user_id="uji")
    for peristiwa in jauh.stream_query(
        user_id="uji", session_id=sesi["id"], message="Tolong uji render PDF sekarang."
    ):
        for bagian in peristiwa.get("content", {}).get("parts", []):
            if bagian.get("text"):
                print("[jauh]", bagian["text"].strip()[:400])
            if bagian.get("function_call"):
                print("[tool]", bagian["function_call"]["name"])


def hapus() -> None:
    c = vertexai.Client(project=PROJECT, location=LOCATION)
    for a in c.agent_engines.list():
        if a.api_resource.display_name == NAMA:
            print("Menghapus", a.api_resource.name)
            c.agent_engines.delete(name=a.api_resource.name, force=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hapus", action="store_true")
    parser.add_argument("--nama")
    argumen = parser.parse_args()
    if argumen.hapus:
        hapus()
        return
    panggil(argumen.nama or deploy())


if __name__ == "__main__":
    main()
