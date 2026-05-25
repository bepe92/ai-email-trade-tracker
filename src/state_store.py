"""Persistent deal store (single source of truth, JSON-backed).

Schema:
  {
    "deals": [
      {
        "id":           "uuid",
        "source_id":    "imap:<Message-ID>" or "local:filename.eml",
        "source_label": "Sender | Subject" or "filename.eml",
        "status":       "pending" | "confirmed" | "auto_rejected" | "manual_rejected",
        "parsed":       {broker, product, volume_mt, price_usd, price_unit, trade_date, reference},
        "errors":       [str, ...]          # set for auto_rejected
        "raw_body":     str                  # the original email text the trader sees
        "created_at":   ISO8601
        "reviewed_by":  str | null           # set after human action
        "reviewed_at":  ISO8601 | null
        "reject_reason": str | null          # set for manual_rejected
      }
    ],
    "processed_ids": [str, ...]   # source_ids that have been ingested (idempotency)
  }
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_AUTO_REJECTED = "auto_rejected"
STATUS_MANUAL_REJECTED = "manual_rejected"


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.deals: list[dict[str, Any]] = []
        self.processed_ids: set[str] = set()
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.deals = data.get("deals", [])
        self.processed_ids = set(data.get("processed_ids", []))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "deals": self.deals,
            "processed_ids": sorted(self.processed_ids),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def reload(self):
        """Re-read state from disk (used by the Flask app on each request)."""
        self.deals = []
        self.processed_ids = set()
        self._load()

    def is_processed(self, source_id: str) -> bool:
        return source_id in self.processed_ids

    def add_deal(
        self,
        source_id: str,
        source_label: str,
        status: str,
        parsed: dict | None,
        errors: list[str],
        raw_body: str,
    ) -> dict:
        if source_id in self.processed_ids:
            return next((d for d in self.deals if d["source_id"] == source_id), {})

        deal = {
            "id": str(uuid.uuid4()),
            "source_id": source_id,
            "source_label": source_label,
            "status": status,
            "parsed": parsed or {},
            "errors": errors,
            "raw_body": raw_body,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "reviewed_by": None,
            "reviewed_at": None,
            "reject_reason": None,
        }
        self.deals.append(deal)
        self.processed_ids.add(source_id)
        return deal

    def find(self, deal_id: str) -> dict | None:
        return next((d for d in self.deals if d["id"] == deal_id), None)

    def by_status(self, status: str) -> list[dict]:
        return [d for d in self.deals if d["status"] == status]

    def counts(self) -> dict[str, int]:
        return {
            STATUS_PENDING: len(self.by_status(STATUS_PENDING)),
            STATUS_CONFIRMED: len(self.by_status(STATUS_CONFIRMED)),
            STATUS_AUTO_REJECTED: len(self.by_status(STATUS_AUTO_REJECTED)),
            STATUS_MANUAL_REJECTED: len(self.by_status(STATUS_MANUAL_REJECTED)),
        }

    def approve(self, deal_id: str, reviewer: str) -> dict | None:
        deal = self.find(deal_id)
        if deal is None or deal["status"] != STATUS_PENDING:
            return None
        deal["status"] = STATUS_CONFIRMED
        deal["reviewed_by"] = reviewer
        deal["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()
        return deal

    def reject(self, deal_id: str, reviewer: str, reason: str) -> dict | None:
        deal = self.find(deal_id)
        if deal is None or deal["status"] != STATUS_PENDING:
            return None
        deal["status"] = STATUS_MANUAL_REJECTED
        deal["reviewed_by"] = reviewer
        deal["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
        deal["reject_reason"] = reason
        self.save()
        return deal
