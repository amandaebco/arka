"""Audit trail for one publication run.

Reproducibility is the thing the infographic gives up. The drawing provider is
not deterministic, so the same finding will not redraw byte for byte, and no
amount of care changes that. What replaces it is a complete record: the finding
that went in, the content assembled from it, the specification that governed the
page, the prompt that was sent, the page that came back, and what the reviewer
found.

Constitution 1.2.0 permits the drawing exception on the strength of its
compensating controls. This module is what makes the third one auditable —
without a trail, "the memo remains the record" is a claim nobody can check.

One folder per run, never overwritten. A run that produced a bad page is as worth
keeping as one that produced a good one.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path("out") / "infografis"

logger = logging.getLogger(__name__)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "temuan"


def _plain(value: Any) -> Any:
    """Coerce dataclasses and pydantic models into something JSON can hold."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


class RunTrail:
    """One folder per run, holding every stage of one publication."""

    def __init__(self, finding_id: str, base: Path | None = None):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.name = f"{stamp}-{_slug(finding_id)}"
        self.prefix = f"infografis/{self.name}"
        self.dir = (base or BASE) / self.name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log: dict[str, Any] = {
            "finding_id": finding_id,
            "started_at": datetime.now().astimezone().isoformat(),
            "rounds": [],
        }

    # --- stages ----------------------------------------------------------

    def record_input(self, finding: Any, content: Any, persona: str, style: str) -> None:
        self.write_json("finding.json", _plain(finding))
        self.write_json("canvas-content.json", _plain(content))
        self.log.update({"persona": persona, "style": style})

    def record_round(
        self,
        index: int,
        spec: Any,
        prompt: str,
        page: bytes | None = None,
        review: Any = None,
    ) -> Path | None:
        """Record one publication round. Returns the page path when one was drawn."""
        self.write_json(f"round-{index}-specification.json", _plain(spec))
        self.write_text(f"round-{index}-prompt.txt", prompt)

        page_path: Path | None = None
        if page is not None:
            page_path = self.dir / f"round-{index}-page.png"
            page_path.write_bytes(page)
            self._mirror(f"round-{index}-page.png", page, "image/png")
        if review is not None:
            self.write_json(f"round-{index}-review.json", _plain(review))

        self.log["rounds"].append(
            {
                "round": index,
                "at": datetime.now().astimezone().isoformat(),
                "specification": _plain(spec),
                "prompt_chars": len(prompt),
                "page_bytes": len(page) if page else 0,
                "review": _plain(review),
            }
        )
        return page_path

    def finish(self, outcome: str, note: str = "") -> Path:
        self.log.update(
            {
                "outcome": outcome,
                "note": note,
                "finished_at": datetime.now().astimezone().isoformat(),
            }
        )
        self.write_json("run.json", self.log)
        return self.dir / "run.json"

    # --- primitives ------------------------------------------------------

    def write_json(self, name: str, data: Any) -> None:
        self.write_text(name, json.dumps(data, indent=2, ensure_ascii=False, default=str))

    def write_text(self, name: str, text: str) -> None:
        (self.dir / name).write_text(text, encoding="utf-8")
        self._mirror(name, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _mirror(self, name: str, payload: bytes, content_type: str) -> None:
        """Copy the file to object storage when one is configured.

        On Cloud Run the container filesystem is ephemeral, so a trail written
        only to local disk disappears with the instance. Since the drawing cannot
        be reproduced, losing the trail means losing the only account of how a
        page came to be — the local copy alone is not a record.

        A mirroring failure is logged and swallowed: the trail is evidence about
        the run, and losing the evidence must never take the run down with it.
        """
        bucket = os.environ.get("ARTIFACT_GCS_BUCKET")
        if not bucket:
            return
        try:
            from google.cloud import storage

            blob = storage.Client().bucket(bucket).blob(f"{self.prefix}/{name}")
            blob.upload_from_string(payload, content_type=content_type)
        except Exception as exc:  # noqa: BLE001 — evidence, never the critical path
            logger.warning("Jejak %s gagal disalin ke GCS: %s", name, exc)
