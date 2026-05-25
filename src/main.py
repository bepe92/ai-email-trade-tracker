"""Batch mode: process all .eml files in sample_emails/ into the state store."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent))

from email_loader import load_eml
from pipeline import process_one_email
from state_store import StateStore, STATUS_PENDING, STATUS_AUTO_REJECTED

ROOT = Path(__file__).parent.parent
SAMPLES_DIR = ROOT / "sample_emails"
OUTPUT_DIR = ROOT / "output"
STATE_PATH = OUTPUT_DIR / "state.json"


def main():
    load_dotenv(ROOT / ".env")
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    state = StateStore(STATE_PATH)

    eml_files = sorted(SAMPLES_DIR.glob("*.eml"))
    print(f"\n{'='*70}")
    print(f"  SHELL DEAL TRACKER - tryb batch ({len(eml_files)} maili)")
    print(f"{'='*70}\n")

    new_count = 0
    for eml_path in eml_files:
        source_id = f"local:{eml_path.name}"
        if state.is_processed(source_id):
            print(f"-- {eml_path.name}  [skip — already processed]")
            continue
        new_count += 1

        email_data = load_eml(eml_path)
        raw_for_review = _build_review_text(email_data)

        status, deal = process_one_email(
            source_id=source_id,
            source_label=eml_path.name,
            body=email_data["body"],
            raw_for_review=raw_for_review,
            state=state,
            client=client,
        )
        _print_result(eml_path.name, status, deal)

    state.save()
    counts = state.counts()

    print(f"{'='*70}")
    print(f"  PODSUMOWANIE")
    print(f"{'='*70}")
    print(f"  Nowych maili w tym uruchomieniu:    {new_count}")
    print(f"  Pending review (czeka na tradera):  {counts[STATUS_PENDING]}")
    print(f"  Auto-rejected (LLM/walidator NIE):  {counts[STATUS_AUTO_REJECTED]}")
    print(f"  Stan: {STATE_PATH}")
    print(f"  Uruchom apkę: python src/app.py\n")


def _build_review_text(email_data: dict) -> str:
    """Pre-format email for the side-by-side review pane."""
    return (
        f"From: {email_data.get('from', '')}\n"
        f"Subject: {email_data.get('subject', '')}\n"
        f"Date: {email_data.get('date', '')}\n"
        f"\n"
        f"{email_data.get('body', '')}"
    )


def _print_result(name: str, status: str, deal: dict | None):
    print(f"-- {name}")
    if status == STATUS_PENDING and deal:
        p = deal["parsed"]
        print(f"   [PENDING REVIEW] {p['broker']} | {p['product']} | "
              f"{p['volume_mt']} MT | {p['price_usd']} USD\n")
    elif status == STATUS_AUTO_REJECTED and deal:
        print(f"   [AUTO-REJECTED]")
        for err in deal["errors"]:
            print(f"      - {err}")
        print()
    else:
        print(f"   [ERROR / SKIP]\n")


if __name__ == "__main__":
    main()
