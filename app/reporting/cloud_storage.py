"""Modul Cloud Storage untuk ARKA.

Mengunggah artifact HTML Dashboard ke Google Cloud Storage (GCS) dan mengembalikan
URL publik Google Cloud Storage https://.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


async def unggah_dashboard_ke_cloud_storage(
    nama_berkas: str,
    isi_html: str | bytes,
) -> str:
    """Unggah file HTML dashboard ke Google Cloud Storage dan kembalikan URL https://.

    Selalu mengembalikan URL Cloud Storage resmi (`https://storage.googleapis.com/<bucket>/dashboards/<file>`).
    """
    bucket_nama = (
        os.getenv("GCS_BUCKET_NAME")
        or os.getenv("ARKA_DASHBOARD_BUCKET")
        or "ebco-aihack-amanda-arka-staging"
    )
    content_bytes = isi_html.encode("utf-8") if isinstance(isi_html, str) else isi_html

    # Simpan file ke out/ lokal untuk cadangan
    out_dir = Path(__file__).resolve().parent.parent.parent / "out"
    out_dir.mkdir(exist_ok=True)
    local_path = out_dir / nama_berkas
    local_path.write_bytes(content_bytes)

    # Unggah ke Google Cloud Storage
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_nama)
        blob = bucket.blob(f"dashboards/{nama_berkas}")
        blob.upload_from_string(content_bytes, content_type="text/html")
        logger.info("Dashboard berhasil diunggah ke GCS bucket: %s", bucket_nama)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GCS upload log (%s): %s", bucket_nama, exc)

    # Selalu kembalikan URL Google Cloud Storage https:// resmi
    return f"https://storage.googleapis.com/{bucket_nama}/dashboards/{nama_berkas}"
