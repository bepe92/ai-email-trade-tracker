"""Quick test for the new Pydantic-based validator.

Proves the original architectural bug is fixed: an LLM that returns 'quantity'
instead of 'volume_mt' would have either crashed downstream or silently
auto-rejected with a useless "missing volume_mt" message. With the new schema,
we get a clear "extra field 'quantity' (model halucynował?)" + the missing
field, all in one shot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validator import validate


CASES = [
    (
        "happy path — valid deal",
        {
            "broker": "Vitol Trading S.A.",
            "product": "Brent Crude Oil",
            "volume_mt": 45000,
            "price_usd": 82.45,
            "price_unit": "per barrel",
            "trade_date": "2026-05-25",
            "reference": "VT-2026-04821",
        },
    ),
    (
        "BUG SCENARIO — LLM hallucinated 'quantity' instead of 'volume_mt'",
        {
            "broker": "Vitol Trading S.A.",
            "product": "Brent Crude Oil",
            "quantity": 45000,                      # WRONG KEY
            "price_usd": 82.45,
            "trade_date": "2026-05-25",
        },
    ),
    (
        "missing required fields (LLM returned null for price)",
        {
            "broker": "Vitol Trading S.A.",
            "product": "Fuel Oil 380 CST",
            "volume_mt": 18000,
            "price_usd": None,
            "trade_date": "2026-05-27",
        },
    ),
    (
        "wrong type — LLM returned 'volume_mt' as string",
        {
            "broker": "Mercuria",
            "product": "Gasoil",
            "volume_mt": "twenty-thousand",         # WRONG TYPE
            "price_usd": 688.75,
            "trade_date": "2026-05-27",
        },
    ),
    (
        "negative volume — LLM did math wrong",
        {
            "broker": "Trafigura",
            "product": "LNG",
            "volume_mt": -75000,                    # NEGATIVE
            "price_usd": 11.20,
            "trade_date": "2026-05-26",
        },
    ),
    (
        "wrong date format (DD/MM/YYYY)",
        {
            "broker": "Glencore",
            "product": "Naphtha",
            "volume_mt": 18000,
            "price_usd": 615.20,
            "trade_date": "27/05/2026",             # NOT ISO
        },
    ),
    (
        "extra surprise field (currency added by LLM)",
        {
            "broker": "Vitol",
            "product": "WTI",
            "volume_mt": 55000,
            "price_usd": 79.85,
            "trade_date": "2026-05-28",
            "currency": "USD",                       # EXTRA UNKNOWN FIELD
        },
    ),
]


def main():
    print("\n" + "="*70)
    print(" PYDANTIC VALIDATOR — TEST SUITE")
    print("="*70 + "\n")

    for i, (label, parsed) in enumerate(CASES, 1):
        is_valid, errors = validate(parsed)
        status = "[VALID]" if is_valid else "[REJECTED]"
        print(f"[{i}] {label}")
        print(f"    -> {status}")
        for err in errors:
            print(f"       - {err}")
        print()


if __name__ == "__main__":
    main()
