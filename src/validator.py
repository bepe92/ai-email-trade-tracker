"""Validate parsed JSON from the LLM using a strict Pydantic schema.

Why Pydantic and not raw dict checks:
  If the LLM hallucinates a different field name (e.g. `quantity` instead of
  `volume_mt`, or `cost` instead of `price_usd`) the old key-presence check
  would accept the response as "missing field" and downstream code accessing
  parsed['volume_mt'] would KeyError. With Pydantic + extra="forbid" we catch
  both halves of the failure (missing required field AND surprise extra field)
  before anything else touches the dict.

Contract preserved:
  validate(parsed) -> (is_valid: bool, errors: list[str])
  Existing callers in pipeline.py do not need to change.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError, field_validator


class DealSchema(BaseModel):
    """Strict schema enforced on every LLM response before downstream code touches it."""

    # extra="forbid" — unknown keys from the LLM are themselves a validation error.
    # If the model drifts (renames volume_mt to quantity) we want to know loudly,
    # not silently route a half-parsed deal to auto_rejected with a useless message.
    model_config = {"extra": "forbid"}

    # Required fields
    broker: str = Field(min_length=1)
    product: str = Field(min_length=1)
    volume_mt: float = Field(gt=0)
    price_usd: float = Field(gt=0)
    trade_date: str

    # Optional fields — None is acceptable (LLM was unsure / not in the email)
    price_unit: str | None = None
    reference: str | None = None

    @field_validator("trade_date")
    @classmethod
    def _date_must_be_iso(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("must be YYYY-MM-DD")
        return v


def validate(parsed: dict) -> tuple[bool, list[str]]:
    """Validate the LLM's parsed output against DealSchema.

    Collects every Pydantic error rather than bailing on the first — gives the
    trader/auditor a complete picture in one shot instead of fix-and-retry.
    """
    try:
        DealSchema.model_validate(parsed)
        return True, []
    except ValidationError as e:
        return False, _format_errors(e)


def _format_errors(e: ValidationError) -> list[str]:
    """Translate Pydantic's machine-readable errors into Polish trader-facing messages."""
    out = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "(root)"
        etype = err["type"]
        raw_input = err.get("input")

        if etype == "missing":
            out.append(f"Brak wymaganego pola: '{loc}'")
        elif etype == "extra_forbidden":
            out.append(f"Nieoczekiwane pole w odpowiedzi LLM: '{loc}' "
                       f"(model halucynował nazwę pola?)")
        elif etype.startswith("greater_than"):
            out.append(f"Pole '{loc}' musi być dodatnie (otrzymano: {raw_input!r})")
        elif etype.startswith(("float_parsing", "int_parsing", "float_type", "int_type")):
            out.append(f"Pole '{loc}' nie jest liczbą (otrzymano: {raw_input!r})")
        elif etype == "string_type":
            out.append(f"Pole '{loc}' nie jest tekstem (otrzymano: {raw_input!r})")
        elif etype == "string_too_short":
            out.append(f"Pole '{loc}' jest puste")
        elif etype == "value_error" and "trade_date" in loc:
            out.append(f"Pole 'trade_date' nie jest w formacie YYYY-MM-DD "
                       f"(otrzymano: {raw_input!r})")
        else:
            # Fallback so we never silently swallow an unhandled validation case.
            out.append(f"Walidacja pola '{loc}' nie powiodła się: {err['msg']}")
    return out
