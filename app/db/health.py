from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.db.session import engine


class HealthResult(TypedDict):
    status: str
    ready: bool
    database: bool
    age_extension: bool
    graph: bool


class DatabaseHealth:
    def __init__(self, database_engine: AsyncEngine, graph_name: str) -> None:
        self._engine = database_engine
        self._graph_name = graph_name

    async def check(self) -> HealthResult:
        result: HealthResult = {
            "status": "unavailable",
            "ready": False,
            "database": False,
            "age_extension": False,
            "graph": False,
        }

        try:
            async with self._engine.connect() as connection:
                result["database"] = bool(await connection.scalar(text("SELECT 1")))
                result["age_extension"] = bool(
                    await connection.scalar(
                        text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'age')")
                    )
                )
                if result["age_extension"]:
                    result["graph"] = bool(
                        await connection.scalar(
                            text(
                                "SELECT EXISTS ("
                                "SELECT 1 FROM ag_catalog.ag_graph WHERE name = :graph_name"
                                ")"
                            ),
                            {"graph_name": self._graph_name},
                        )
                    )
        except SQLAlchemyError:
            return result

        result["ready"] = all((result["database"], result["age_extension"], result["graph"]))
        result["status"] = "ok" if result["ready"] else "unavailable"
        return result


def get_database_health() -> DatabaseHealth:
    settings = get_settings()
    return DatabaseHealth(engine, settings.age_graph_name)
