"""Seed the state store with extra mock deals across multiple days for a realistic briefing.

This is one-shot data enrichment for demo purposes — generates a believable
trading week without spamming the LLM API. Inserts directly into state.json
with hand-picked status / timestamps so the briefing has rich material to summarise.
"""
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from state_store import (
    StateStore,
    STATUS_CONFIRMED,
    STATUS_MANUAL_REJECTED,
    STATUS_PENDING,
)

STATE_PATH = Path(__file__).parent.parent / "output" / "state.json"
REVIEWER = "trader@shell.com"

# Realistic broker/product matrix for mock data
EXTRA_DEALS = [
    # ===== Day -2 (two days ago) — fully closed out =====
    ("Vitol Trading S.A.",      "Brent Crude Oil",            68000, 82.10, "per barrel",        "VT-2026-04830", -2, STATUS_CONFIRMED),
    ("Trafigura Markets Ltd",   "Natural Gas (Henry Hub)",    95000,  3.92, "per MMBtu",         "TFG-29420",     -2, STATUS_CONFIRMED),
    ("Mercuria Energy Trading", "Gasoil 0.1%",                28000, 690.20,"per MT",            "ME/2026/00730", -2, STATUS_CONFIRMED),
    ("Vitol Trading S.A.",      "Jet Fuel A1",                12000, 951.40,"per MT",            "VT-2026-04832", -2, STATUS_CONFIRMED),
    ("Glencore Energy UK Ltd",  "Fuel Oil 380 CST",           22000, 485.75,"per MT",            "GLN-2026-7711", -2, STATUS_MANUAL_REJECTED),

    # ===== Day -1 (yesterday) — mostly closed =====
    ("Trafigura Markets Ltd",   "LNG (Liquefied Natural Gas)",80000, 11.45, "per MMBtu",         "TFG-29428",     -1, STATUS_CONFIRMED),
    ("Vitol Trading S.A.",      "ULSD (Ultra Low Sulphur Diesel)", 35000, 728.30, "per MT",     "VT-2026-04838", -1, STATUS_CONFIRMED),
    ("Mercuria Energy Trading", "Brent Crude Oil",            42000, 82.65, "per barrel",        "ME/2026/00738", -1, STATUS_CONFIRMED),
    ("Glencore Energy UK Ltd",  "Naphtha",                    18000, 615.20,"per MT",            "GLN-2026-7724", -1, STATUS_CONFIRMED),
    ("Vitol Trading S.A.",      "WTI Crude Oil",              55000, 79.40, "per barrel",        "VT-2026-04841", -1, STATUS_CONFIRMED),

    # ===== Day 0 (today) — mix of confirmed + still pending =====
    ("Trafigura Markets Ltd",   "Natural Gas (Henry Hub)",   110000,  3.88, "per MMBtu",         "TFG-29435",      0, STATUS_CONFIRMED),
    ("Mercuria Energy Trading", "Jet Fuel A1",                 9500, 948.00,"per MT",            "ME/2026/00742",  0, STATUS_CONFIRMED),
    ("Vitol Trading S.A.",      "Brent Crude Oil",            48000, 84.05, "per barrel",        "VT-2026-04845",  0, STATUS_PENDING),
    ("Glencore Energy UK Ltd",  "Gasoil 0.1%",                25000, 688.90,"per MT",            "GLN-2026-7731",  0, STATUS_PENDING),
]


def _mk_raw_body(broker: str, product: str, volume: int, price: float, unit: str, ref: str, dt: datetime) -> str:
    return (
        f"From: deals@{broker.lower().split()[0]}.com\n"
        f"Subject: [SHELL DEAL] {broker.split()[0]} - {product} confirmation\n"
        f"Date: {dt.strftime('%a, %d %b %Y %H:%M:%S +0000')}\n"
        f"\n"
        f"Dear Trading Desk,\n\n"
        f"Deal confirmation as below:\n\n"
        f"Reference:  {ref}\n"
        f"Trade Date: {dt.strftime('%d-%b-%Y')}\n"
        f"Product:    {product}\n"
        f"Volume:     {volume:,} MT\n"
        f"Price:      {price} USD {unit}\n"
        f"\nBest regards,\n{broker}"
    )


def main():
    state = StateStore(STATE_PATH)
    now = datetime.now()
    added = 0

    for broker, product, volume, price, unit, ref, day_offset, status in EXTRA_DEALS:
        # Place each deal at a varied time on the offset day
        hour = 8 + (added % 9)  # spread between 08:00 and 17:00
        minute = (added * 7) % 60
        created_dt = (now + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        reviewed_dt = created_dt + timedelta(minutes=15)

        source_id = f"seed:{ref}"
        if state.is_processed(source_id):
            continue

        deal = {
            "id": str(uuid.uuid4()),
            "source_id": source_id,
            "source_label": f"deals@{broker.lower().split()[0]}.com | [SHELL DEAL] {ref}",
            "status": status,
            "parsed": {
                "broker": broker,
                "product": product,
                "volume_mt": volume,
                "price_usd": price,
                "price_unit": unit,
                "trade_date": created_dt.strftime("%Y-%m-%d"),
                "reference": ref,
            },
            "errors": [],
            "raw_body": _mk_raw_body(broker, product, volume, price, unit, ref, created_dt),
            "created_at": created_dt.isoformat(timespec="seconds"),
            "reviewed_by": REVIEWER if status in (STATUS_CONFIRMED, STATUS_MANUAL_REJECTED) else None,
            "reviewed_at": reviewed_dt.isoformat(timespec="seconds") if status in (STATUS_CONFIRMED, STATUS_MANUAL_REJECTED) else None,
            "reject_reason": "Broker disputed pricing — deal voided per ops call" if status == STATUS_MANUAL_REJECTED else None,
        }
        state.deals.append(deal)
        state.processed_ids.add(source_id)
        added += 1

    state.save()
    print(f"Added {added} seed deals across 3 days.")
    counts = state.counts()
    print(f"  Pending:          {counts[STATUS_PENDING]}")
    print(f"  Confirmed:        {counts[STATUS_CONFIRMED]}")
    print(f"  Manual rejected:  {counts[STATUS_MANUAL_REJECTED]}")
    print(f"  Auto-rejected:    {counts['auto_rejected']}")
    print(f"  TOTAL:            {sum(counts.values())}")


if __name__ == "__main__":
    main()
