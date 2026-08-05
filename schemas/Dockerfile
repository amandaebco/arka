# PostgreSQL 16 + Apache AGE + pgvector.
#
# Image resmi apache/age hanya tersedia untuk amd64 dan tidak memuat pgvector,
# jadi AGE dikompilasi di atas image pgvector (multi-arch) agar jalan native
# di Apple Silicon maupun x86.
FROM pgvector/pgvector:pg16

ARG AGE_VERSION=PG16/v1.6.0-rc0

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential ca-certificates git flex bison \
        postgresql-server-dev-16 libreadline-dev zlib1g-dev; \
    git clone --depth 1 --branch "${AGE_VERSION}" https://github.com/apache/age.git /tmp/age; \
    make -C /tmp/age install; \
    rm -rf /tmp/age; \
    apt-get purge -y --auto-remove build-essential git flex bison postgresql-server-dev-16; \
    rm -rf /var/lib/apt/lists/*
