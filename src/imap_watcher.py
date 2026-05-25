"""IMAP watcher: poll Gmail for unread Deal Confirmation emails and queue them for human review."""
import email
import imaplib
import os
import sys
import time
from datetime import datetime
from email import policy
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent))

from email_loader import _html_to_text
from pipeline import process_one_email
from state_store import StateStore, STATUS_PENDING, STATUS_AUTO_REJECTED

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
STATE_PATH = OUTPUT_DIR / "state.json"

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SUBJECT_FILTER = "[SHELL DEAL]"
POLL_INTERVAL_SEC = 30


def main():
    load_dotenv(ROOT / ".env")
    for var in ("ANTHROPIC_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"):
        if var not in os.environ or not os.environ[var]:
            print(f"ERROR: {var} not set in .env")
            sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    state = StateStore(STATE_PATH)

    address = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    counts = state.counts()
    print(f"\n{'='*70}")
    print(f"  SHELL DEAL TRACKER - tryb LIVE (IMAP watcher)")
    print(f"{'='*70}")
    print(f"  Inbox:           {address}")
    print(f"  Filtr Subject:   '{SUBJECT_FILTER}'")
    print(f"  Polling:         co {POLL_INTERVAL_SEC}s")
    print(f"  Stan: pending={counts[STATUS_PENDING]} auto_rejected={counts[STATUS_AUTO_REJECTED]}")
    print(f"  Trader review UI: http://localhost:5000")
    print(f"  Ctrl+C zatrzymuje")
    print(f"{'='*70}\n")

    try:
        while True:
            try:
                # Refresh state from disk each cycle so we see approvals/rejections made via the UI.
                state.reload()
                _poll_once(address, password, client, state)
            except imaplib.IMAP4.error as e:
                print(f"[{_ts()}] IMAP error: {e} (retry in {POLL_INTERVAL_SEC}s)")
            except Exception as e:
                print(f"[{_ts()}] Unexpected error: {e} (retry in {POLL_INTERVAL_SEC}s)")

            time.sleep(POLL_INTERVAL_SEC)
    except KeyboardInterrupt:
        print(f"\n[{_ts()}] Stopped by user.")


def _poll_once(address: str, password: str, client: Anthropic, state: StateStore):
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(address, password)
        imap.select("INBOX")

        typ, data = imap.search(None, "UNSEEN", f'SUBJECT "{SUBJECT_FILTER}"')
        if typ != "OK":
            print(f"[{_ts()}] IMAP search failed: {typ}")
            return

        msg_nums = data[0].split()
        if not msg_nums:
            print(f"[{_ts()}] no new messages")
            return

        print(f"[{_ts()}] found {len(msg_nums)} new message(s)")
        any_processed = False

        for num in msg_nums:
            typ, msg_data = imap.fetch(num, "(RFC822)")
            if typ != "OK":
                print(f"   fetch failed for msg {num!r}")
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=policy.default)

            sender = msg.get("From", "?")
            subject = msg.get("Subject", "(no subject)")
            date_hdr = msg.get("Date", "")
            source_id = f"imap:{msg.get('Message-ID', f'noid-{num.decode()}')}"
            source_label = f"{sender} | {subject}"

            body = _extract_body(msg)
            raw_for_review = (
                f"From: {sender}\n"
                f"Subject: {subject}\n"
                f"Date: {date_hdr}\n"
                f"\n"
                f"{body}"
            )

            status, deal = process_one_email(
                source_id=source_id,
                source_label=source_label,
                body=body,
                raw_for_review=raw_for_review,
                state=state,
                client=client,
            )

            if status == STATUS_PENDING and deal:
                p = deal["parsed"]
                print(f"   [PENDING REVIEW] {p['broker']} | {p['product']} | "
                      f"{p['volume_mt']} MT | {p['price_usd']} USD")
            elif status == STATUS_AUTO_REJECTED and deal:
                print(f"   [AUTO-REJECTED] {source_label}")
                for err in deal["errors"]:
                    print(f"      - {err}")
            elif status == "ERROR" and deal:
                print(f"   [ERROR] {source_label}: {'; '.join(deal['errors'])}")
            else:
                print(f"   [SKIP] {source_label}")

            imap.store(num, "+FLAGS", "\\Seen")
            any_processed = True

        if any_processed:
            state.save()


def _extract_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                body = part.get_content()
                break
            elif ctype == "text/html" and not body:
                body = _html_to_text(part.get_content())
    else:
        content = msg.get_content()
        if msg.get_content_type() == "text/html":
            body = _html_to_text(content)
        else:
            body = content
    return body.strip()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    main()
