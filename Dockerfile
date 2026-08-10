# Image ARKA — dipakai bersama Cloud Run dan Agent Engine (`image_spec`).
#
# Chromium dipanggang ke dalam image, dan itu keputusan yang sudah dibayar mahal:
# ia tidak bisa dipasang lewat `installation_scripts` Agent Engine (divalidasi SDK
# lalu tidak pernah dikirim ke API), dan pemasangan saat runtime melebihi anggaran
# waktu satu permintaan. Dengan image ini, render PDF berjalan di mana pun.
#
# Basisnya slim, bukan image resmi Playwright: yang resmi memuat tiga peramban
# (~4,3 GB) padahal kita hanya memakai satu. Ukuran image langsung terasa pada
# cold start Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Dependensi lebih dulu, terpisah dari kode, supaya lapisan ini ikut ter-cache
# selama pyproject tidak berubah.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Hanya Chromium, beserta pustaka sistemnya. Versi biner mengikuti paket
# `playwright` yang barusan terpasang — keduanya harus sepadan.
RUN playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8080

# Cloud Run menyuntikkan PORT. `adk_agents/` berisi pembungkus tipis karena ADK
# menuntut satu direktori per agent — lihat adk_agents/README.md.
# `ARTIFACT_GCS_BUCKET` menentukan ke mana artifact disimpan. Tanpa itu ADK
# memakai penyimpanan dalam memori, dan keluaran hilang begitu instance didaur
# ulang — tidak terlihat saat demo, fatal untuk keterlacakan.
CMD ["sh", "-c", "exec adk api_server adk_agents --host 0.0.0.0 --port ${PORT:-8080} ${ARTIFACT_GCS_BUCKET:+--artifact_service_uri=gs://$ARTIFACT_GCS_BUCKET}"]
