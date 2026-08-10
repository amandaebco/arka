"""Deploy to Agent Engine using the same image as Cloud Run.

The pickle path works but ships no Chromium, so a reporter deployed that way
fails to publish — loudly, since the HTML fallback was deliberately removed.
This path hands Agent Engine our own Dockerfile instead, the one already proven
on Cloud Run, so both runtimes run the same bytes.

    uv run python scripts/deploy_image.py
    uv run python scripts/deploy_image.py --hapus
"""

import argparse

import vertexai

PROJECT = "ebco-aihack-amanda"
LOCATION = "us-central1"
BUCKET = "gs://ebco-aihack-amanda-arka-staging"
NAMA = "arka-image"


def klien() -> vertexai.Client:
    return vertexai.Client(project=PROJECT, location=LOCATION)


def deploy() -> str:
    c = klien()
    print("Mengunggah sumber dan membangun image — ini lama…")
    hasil = c.agent_engines.create(
        config={
            "display_name": NAMA,
            "description": "ARKA lewat image yang sama dengan Cloud Run",
            "staging_bucket": BUCKET,
            # Dockerfile ikut terkirim; Agent Engine yang membangunnya.
            "source_packages": [
                "app",
                "adk_agents",
                "Dockerfile",
                "pyproject.toml",
                "README.md",
            ],
            "image_spec": {"build_args": {}},
            "env_vars": {
                "GOOGLE_CLOUD_LOCATION": "global",
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
            },
        },
    )
    nama = hasil.api_resource.name
    print("RESOURCE:", nama)
    return nama


def hapus() -> None:
    c = klien()
    for a in c.agent_engines.list():
        if a.api_resource.display_name == NAMA:
            print("Menghapus", a.api_resource.name)
            c.agent_engines.delete(name=a.api_resource.name, force=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hapus", action="store_true")
    if parser.parse_args().hapus:
        hapus()
        return
    deploy()


if __name__ == "__main__":
    main()
