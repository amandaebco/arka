import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Manufacturing Knowledge Graph API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "manufacturing_kg"
    postgres_user: str = "manufacturing"
    postgres_password: str = Field(default="manufacturing", repr=False)
    postgres_echo: bool = False

    age_graph_name: str = "manufacturing_kg"
    document_storage_path: Path = Path("data/documents")
    max_document_bytes: int = Field(default=25_000_000, gt=0)

    # Project dan lokasi Vertex TIDAK disetel di sini. ADK memanggil lewat
    # `google-genai`, yang membaca `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
    # dan `GOOGLE_GENAI_USE_VERTEXAI` langsung dari lingkungan. Menyimpan salinan
    # di sini dulu membuat dua sumber kebenaran yang diam-diam berbeda.
    # Dibaca dari `GEMINI_MODEL` — nama yang sudah dipakai di `.env` — dengan
    # `VERTEX_AI_MODEL` tetap diterima sebagai nama bawaan pydantic-settings.
    vertex_ai_model: str = Field(
        default="gemini-3.6-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "VERTEX_AI_MODEL"),
    )
    vertex_ai_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    vertex_ai_fallback_enabled: bool = True

    # Penggambar infografis. Satu-satunya jalur di ARKA yang memanggil penyedia
    # di luar Google — dipilih sadar untuk memperluas keragaman tumpukan, dan
    # isinya terbatas pada nilai yang sudah ada di `Finding`
    # (Constitution 1.2.0, pengecualian infografis).
    # `openai` memakai gpt-image-2 dan menuntut IMAGE_API_KEY; `vertex` memakai
    # model gambar Gemini lewat project yang sama dengan pembaca halaman, jadi ia
    # tetap jalan ketika kredit OpenAI habis.
    # Salinan permanen jejak penerbitan. Kosong berarti jejak hanya ada di disk
    # lokal — di Cloud Run itu berarti hilang bersama instance-nya.
    artifact_gcs_bucket: str = ""

    image_provider: str = "openai"
    image_api_key: str = Field(default="", repr=False)
    image_model: str = "gpt-image-2"
    image_model_vertex: str = "gemini-3-pro-image"
    image_size: str = "1024x1536"
    image_quality: str = "high"
    image_timeout_seconds: float = Field(default=180.0, gt=0, le=600)

    @property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Nama variabel yang dibaca `google-genai` langsung dari lingkungan proses.
_ENV_VERTEX = (
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_GENAI_USE_VERTEXAI",
)


def terapkan_env_vertex() -> dict[str, str]:
    """Salin setelan Vertex dari `.env` ke lingkungan proses.

    `Settings` membaca `.env` ke dalam objek Python, sedangkan `google-genai`
    membaca `os.environ`. Tanpa jembatan ini, mengisi `.env` tidak berpengaruh
    apa pun terhadap tujuan panggilan model — dan panggilan diam-diam jatuh ke
    default gcloud, yang bisa berbeda di mesin lain.

    Variabel yang sudah ada di lingkungan **tidak ditimpa**: perintah yang
    menyetelnya secara eksplisit tetap menang.

    Returns:
        Variabel yang benar-benar disetel oleh fungsi ini.
    """
    from dotenv import dotenv_values

    berkas = dotenv_values(".env")
    disetel: dict[str, str] = {}
    for nama in _ENV_VERTEX:
        nilai = berkas.get(nama)
        if nilai and not os.environ.get(nama):
            os.environ[nama] = nilai
            disetel[nama] = nilai
    return disetel
