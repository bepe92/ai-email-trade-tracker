"""Validate parsed JSON. Route to path A (success) or path B (human review)."""
from datetime import datetime

REQUIRED_FIELDS = ["broker", "product", "volume_mt", "price_usd", "trade_date"]


def validate(parsed: dict) -> tuple[bool, list[str]]:
    """Return (is_valid, list_of_errors)."""
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in parsed or parsed[field] is None:
            errors.append(f"Brak wymaganego pola: '{field}'")

    if parsed.get("volume_mt") is not None:
        if not isinstance(parsed["volume_mt"], (int, float)):
            errors.append(f"Pole 'volume_mt' nie jest liczbą: {parsed['volume_mt']!r}")
        elif parsed["volume_mt"] <= 0:
            errors.append(f"Pole 'volume_mt' musi być dodatnie: {parsed['volume_mt']}")

    if parsed.get("price_usd") is not None:
        if not isinstance(parsed["price_usd"], (int, float)):
            errors.append(f"Pole 'price_usd' nie jest liczbą: {parsed['price_usd']!r}")
        elif parsed["price_usd"] <= 0:
            errors.append(f"Pole 'price_usd' musi być dodatnie: {parsed['price_usd']}")

    if parsed.get("trade_date"):
        try:
            datetime.strptime(parsed["trade_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            errors.append(f"Pole 'trade_date' nie jest w formacie YYYY-MM-DD: {parsed['trade_date']!r}")

    return len(errors) == 0, errors
