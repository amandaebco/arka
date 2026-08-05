import json
from dataclasses import dataclass
from typing import Any

from app.graph.competency import QUERY_BY_ID
from app.graph.dynamic_cypher import GRAPH_SCHEMA

AGGREGATE_QUERY_IDS = {
    "top-equipment-by-work-orders",
    "maintenance-volume-by-plant",
}
GOOGLE_CLOUD_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class VertexAIPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class VertexAIPlan:
    query_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    citations: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class DynamicCypherPlan:
    cypher: str
    rationale: str


def _planner_prompt(question: str) -> str:
    options = "\n".join(
        f"- {query.id}: {query.question}"
        for query in QUERY_BY_ID.values()
    )
    return f"""Pilih competency query yang diperlukan untuk menjawab pertanyaan pengguna.

Query yang tersedia:
{options}

Aturan:
- Pilih hanya ID dari daftar.
- Boleh memilih beberapa ID untuk pertanyaan gabungan.
- Jangan membuat Cypher.
- Jangan gabungkan query agregat lintas equipment dengan query untuk satu equipment.
- Jika pertanyaan tidak dapat dijawab oleh daftar tersebut, kembalikan query_ids kosong.
- rationale harus berupa alasan klasifikasi singkat, bukan penalaran panjang.

Pertanyaan pengguna:
{question}
"""


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query_ids": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(QUERY_BY_ID),
                },
                "maxItems": 3,
            },
            "rationale": {
                "type": "string",
                "description": "Alasan klasifikasi yang singkat.",
            },
        },
        "required": ["query_ids", "rationale"],
    }


def build_graph_context(
    results: list[dict[str, Any]],
    max_rows_per_query: int = 20,
) -> dict[str, Any]:
    facts = []
    for result in results:
        for index, row in enumerate(
            result.get("rows", [])[:max_rows_per_query],
            start=1,
        ):
            facts.append(
                {
                    "source_ref": f"{result['query_id']}#{index}",
                    "retrieval_question": result["question"],
                    "fact": row,
                }
            )
    return {"facts": facts}


def _grounded_answer_prompt(question: str, context: dict[str, Any]) -> str:
    return f"""Anda adalah asisten maintenance yang menjawab berdasarkan graph context.

Aturan grounding:
- Gunakan hanya fakta pada graph context.
- Jangan menambahkan cause, damage, aktivitas, tanggal, atau rekomendasi yang tidak tersedia.
- Jangan mengubah hubungan korelasi menjadi sebab-akibat baru.
- Pertahankan review_status dan confidence jika relevan.
- Jawab ringkas dalam Bahasa Indonesia.
- citations hanya boleh berisi source_ref yang benar-benar mendukung jawaban.
- Jika data tidak cukup, jelaskan pada limitations.

Pertanyaan pengguna:
{question}

Graph context:
{json.dumps(context, ensure_ascii=False)}
"""


def _grounded_answer_schema(source_refs: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {"type": "string", "enum": source_refs},
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["answer", "citations", "limitations"],
    }


def _dynamic_cypher_prompt(
    question: str,
    tag_number: str | None,
    max_limit: int,
) -> str:
    return f"""Buat satu query openCypher read-only untuk Apache AGE.

Graph schema:
{GRAPH_SCHEMA}

Aturan wajib:
- Hanya gunakan MATCH, OPTIONAL MATCH, WHERE, WITH, RETURN, ORDER BY, LIMIT.
- Hanya gunakan label, relationship, dan property dari schema.
- Maksimal tiga relationship/hop.
- Dilarang variable-length traversal.
- Dilarang string literal dan raw parameter.
- Jika perlu equipment terpilih, gunakan placeholder __TAG_NUMBER__ tanpa tanda kutip.
- Nilai asli tag number tidak diberikan; jangan membuat atau menebaknya.
- Return harus tepat satu map dengan bentuk RETURN {{field: value}} AS row.
- Untuk agregasi per group, return satu map per group; jangan gunakan collect dengan nested map.
- Semua count/sum/avg/min/max wajib dihitung di WITH sebagai alias.
- RETURN map hanya boleh memakai alias hasil agregasi, jangan panggil fungsi agregasi di RETURN.
- Wajib satu LIMIT numerik antara 1 dan {max_limit}.
- Jangan gunakan CREATE, MERGE, DELETE, SET, REMOVE, CALL, LOAD, UNION, atau komentar.

Equipment terpilih tersedia:
{"ya" if tag_number else "tidak"}

Pertanyaan pengguna:
{question}
"""


def _dynamic_cypher_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "cypher": {"type": "string"},
            "rationale": {
                "type": "string",
                "description": "Penjelasan singkat pola graph yang dipilih.",
            },
        },
        "required": ["cypher", "rationale"],
    }


def _repair_cypher_prompt(
    question: str,
    failed_cypher: str,
    validation_error: str,
    tag_number: str | None,
    max_limit: int,
) -> str:
    return (
        _dynamic_cypher_prompt(question, tag_number, max_limit)
        + f"""

Query sebelumnya ditolak:
{failed_cypher}

Error validator atau Apache AGE:
{validation_error}

Perbaiki query satu kali dengan tetap mengikuti seluruh aturan.
"""
    )


def _validate_grounded_answer(
    payload: dict[str, Any],
    source_refs: set[str],
) -> GroundedAnswer:
    answer = payload.get("answer")
    citations = payload.get("citations")
    limitations = payload.get("limitations")
    if (
        not isinstance(answer, str)
        or not isinstance(citations, list)
        or not isinstance(limitations, list)
        or any(not isinstance(item, str) for item in citations + limitations)
    ):
        raise VertexAIPlannerError("Vertex AI returned an invalid grounded answer")
    if not citations or any(citation not in source_refs for citation in citations):
        raise VertexAIPlannerError("Vertex AI returned invalid graph citations")
    return GroundedAnswer(
        answer=answer.strip(),
        citations=tuple(dict.fromkeys(citations)),
        limitations=tuple(limitations),
    )


def _validate_plan(payload: dict[str, Any]) -> VertexAIPlan:
    query_ids = payload.get("query_ids")
    rationale = payload.get("rationale")
    if not isinstance(query_ids, list) or not isinstance(rationale, str):
        raise VertexAIPlannerError("Vertex AI returned an invalid planner response")
    if len(query_ids) > 3 or len(set(query_ids)) != len(query_ids):
        raise VertexAIPlannerError("Vertex AI returned invalid query selection")
    if any(query_id not in QUERY_BY_ID for query_id in query_ids):
        raise VertexAIPlannerError("Vertex AI selected a query outside the allowlist")
    has_aggregate = any(query_id in AGGREGATE_QUERY_IDS for query_id in query_ids)
    if has_aggregate and len(query_ids) > 1:
        raise VertexAIPlannerError(
            "Vertex AI mixed aggregate and equipment-scoped queries"
        )
    return VertexAIPlan(tuple(query_ids), rationale.strip())


def _create_client(
    project: str,
    location: str,
    timeout_seconds: float,
):
    from google import genai
    from google.genai.types import HttpOptions

    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=HttpOptions(
            api_version="v1",
            timeout=int(timeout_seconds * 1000),
        ),
    )


def adc_credentials_available() -> bool:
    try:
        import google.auth

        google.auth.default(scopes=[GOOGLE_CLOUD_SCOPE])
    except Exception:
        return False
    return True


def plan_with_vertex_ai(
    question: str,
    project: str,
    location: str,
    model: str,
    timeout_seconds: float = 15,
) -> VertexAIPlan:
    try:
        client = _create_client(project, location, timeout_seconds)
        response = client.models.generate_content(
            model=model,
            contents=_planner_prompt(question),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": _response_schema(),
            },
        )
        if not response.text:
            raise VertexAIPlannerError("Vertex AI returned an empty response")
        return _validate_plan(json.loads(response.text))
    except VertexAIPlannerError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise VertexAIPlannerError("Vertex AI returned an unreadable response") from exc
    except Exception as exc:
        raise VertexAIPlannerError(f"Vertex AI request failed: {exc}") from exc


def generate_grounded_answer(
    question: str,
    results: list[dict[str, Any]],
    project: str,
    location: str,
    model: str,
    timeout_seconds: float = 15,
) -> GroundedAnswer:
    context = build_graph_context(results)
    source_refs = [fact["source_ref"] for fact in context["facts"]]
    if not source_refs:
        raise VertexAIPlannerError("Graph retrieval returned no facts to ground an answer")
    try:
        client = _create_client(project, location, timeout_seconds)
        response = client.models.generate_content(
            model=model,
            contents=_grounded_answer_prompt(question, context),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": _grounded_answer_schema(source_refs),
            },
        )
        if not response.text:
            raise VertexAIPlannerError("Vertex AI returned an empty grounded answer")
        return _validate_grounded_answer(
            json.loads(response.text),
            set(source_refs),
        )
    except VertexAIPlannerError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise VertexAIPlannerError("Vertex AI returned an unreadable answer") from exc
    except Exception as exc:
        raise VertexAIPlannerError(
            f"Vertex AI grounded answer request failed: {exc}"
        ) from exc


def generate_dynamic_cypher(
    question: str,
    tag_number: str | None,
    max_limit: int,
    project: str,
    location: str,
    model: str,
    timeout_seconds: float = 15,
) -> DynamicCypherPlan:
    try:
        client = _create_client(project, location, timeout_seconds)
        response = client.models.generate_content(
            model=model,
            contents=_dynamic_cypher_prompt(question, tag_number, max_limit),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": _dynamic_cypher_schema(),
            },
        )
        if not response.text:
            raise VertexAIPlannerError("Vertex AI returned empty Cypher")
        payload = json.loads(response.text)
        cypher = payload.get("cypher")
        rationale = payload.get("rationale")
        if not isinstance(cypher, str) or not isinstance(rationale, str):
            raise VertexAIPlannerError("Vertex AI returned invalid Cypher output")
        return DynamicCypherPlan(cypher.strip(), rationale.strip())
    except VertexAIPlannerError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise VertexAIPlannerError("Vertex AI returned unreadable Cypher output") from exc
    except Exception as exc:
        raise VertexAIPlannerError(
            f"Vertex AI text-to-Cypher request failed: {exc}"
        ) from exc


def repair_dynamic_cypher(
    question: str,
    failed_cypher: str,
    validation_error: str,
    tag_number: str | None,
    max_limit: int,
    project: str,
    location: str,
    model: str,
    timeout_seconds: float = 15,
) -> DynamicCypherPlan:
    try:
        client = _create_client(project, location, timeout_seconds)
        response = client.models.generate_content(
            model=model,
            contents=_repair_cypher_prompt(
                question,
                failed_cypher,
                validation_error,
                tag_number,
                max_limit,
            ),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": _dynamic_cypher_schema(),
            },
        )
        if not response.text:
            raise VertexAIPlannerError("Vertex AI returned empty repaired Cypher")
        payload = json.loads(response.text)
        cypher = payload.get("cypher")
        rationale = payload.get("rationale")
        if not isinstance(cypher, str) or not isinstance(rationale, str):
            raise VertexAIPlannerError("Vertex AI returned invalid repaired Cypher")
        return DynamicCypherPlan(cypher.strip(), rationale.strip())
    except VertexAIPlannerError:
        raise
    except Exception as exc:
        raise VertexAIPlannerError(
            f"Vertex AI Cypher repair failed: {exc}"
        ) from exc
