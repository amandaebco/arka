"""Connection string helper untuk klien psycopg sinkron (proyeksi graph, query GQL/Cypher)."""

from app.core.config import get_settings


def connection_string() -> str:
    settings = get_settings()
    return (
        f"host={settings.postgres_host} "
        f"port={settings.postgres_port} "
        f"dbname={settings.postgres_db} "
        f"user={settings.postgres_user} "
        f"password={settings.postgres_password}"
    )
