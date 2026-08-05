import re
from dataclasses import dataclass

from app.graph.competency import QUERY_BY_ID


@dataclass(frozen=True)
class RoutedQuestion:
    query_ids: tuple[str, ...]
    strategy: str = "allowlist"


INTENT_PATTERNS = (
    (
        "verified-causes",
        re.compile(r"\b(penyebab|cause|causes|akar masalah|root cause)\b", re.IGNORECASE),
    ),
    (
        "reported-damages",
        re.compile(
            r"\b(damage|damages|kerusakan|rusak|kebocoran|leaking)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "affected-parts",
        re.compile(
            r"\b(object part|bagian|komponen|component|part)\b",
            re.IGNORECASE,
        ),
    ),
)
TOP_EQUIPMENT_PATTERN = re.compile(
    r"\b(terbanyak|paling banyak|tertinggi|top)\b.*\b(work order|wo)\b"
    r"|\b(work order|wo)\b.*\b(terbanyak|paling banyak|tertinggi|top)\b",
    re.IGNORECASE,
)
PLANT_VOLUME_PATTERN = re.compile(
    r"\b(per plant|setiap plant|berdasarkan plant|volume maintenance)\b",
    re.IGNORECASE,
)
MAINTENANCE_PATTERN = re.compile(
    r"\b(work order|notification|notifikasi|riwayat|histori|maintenance|pemeliharaan)\b",
    re.IGNORECASE,
)


def route_question(question: str) -> RoutedQuestion:
    normalized = " ".join(question.split())
    if TOP_EQUIPMENT_PATTERN.search(normalized):
        return RoutedQuestion(("top-equipment-by-work-orders",))
    if PLANT_VOLUME_PATTERN.search(normalized):
        return RoutedQuestion(("maintenance-volume-by-plant",))

    query_ids = tuple(
        query_id
        for query_id, pattern in INTENT_PATTERNS
        if pattern.search(normalized)
    )
    if not query_ids and MAINTENANCE_PATTERN.search(normalized):
        query_ids = ("maintenance-history",)
    if not query_ids:
        raise ValueError("unsupported_question")
    if any(query_id not in QUERY_BY_ID for query_id in query_ids):
        raise RuntimeError("Router selected an unknown query")
    return RoutedQuestion(query_ids)


def summarize_results(results: list[dict]) -> str:
    labels = {
        "maintenance-history": "riwayat maintenance",
        "verified-causes": "cause terverifikasi",
        "reported-damages": "damage terverifikasi",
        "affected-parts": "object part terdampak",
        "top-equipment-by-work-orders": "equipment",
        "maintenance-volume-by-plant": "plant",
    }
    findings = [
        f"{result['row_count']} {labels[result['query_id']]}"
        for result in results
        if result["row_count"]
    ]
    if not findings:
        return "Belum ditemukan fakta terverifikasi untuk pertanyaan ini."
    return "Ditemukan " + ", ".join(findings) + "."
