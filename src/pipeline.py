"""Single-deal processing logic shared by batch and IMAP watcher modes.

Routing:
  - Validator fails  -> status = auto_rejected (no human action needed)
  - Validator passes -> status = pending       (queued for human approval in the Flask app)
"""
from anthropic import Anthropic

from parser import parse_email
from state_store import (
    StateStore,
    STATUS_AUTO_REJECTED,
    STATUS_PENDING,
)
from validator import validate


def process_one_email(
    source_id: str,
    source_label: str,
    body: str,
    raw_for_review: str,
    state: StateStore,
    client: Anthropic,
) -> tuple[str, dict | None]:
    """Parse + validate one email, persist to state.

    Returns (status, deal) where status is "pending" | "auto_rejected" | "ERROR" | "SKIP".
    """
    if state.is_processed(source_id):
        return "SKIP", None

    try:
        parsed = parse_email(body, client=client)
    except Exception as e:
        errors = [f"Parser exception: {e}"]
        deal = state.add_deal(
            source_id=source_id,
            source_label=source_label,
            status=STATUS_AUTO_REJECTED,
            parsed=None,
            errors=errors,
            raw_body=raw_for_review,
        )
        return "ERROR", deal

    is_valid, errors = validate(parsed)
    status = STATUS_PENDING if is_valid else STATUS_AUTO_REJECTED
    deal = state.add_deal(
        source_id=source_id,
        source_label=source_label,
        status=status,
        parsed=parsed,
        errors=errors,
        raw_body=raw_for_review,
    )
    return status, deal
