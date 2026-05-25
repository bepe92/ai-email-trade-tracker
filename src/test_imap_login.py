"""One-shot IMAP login test — verify Gmail credentials before running the watcher."""
import imaplib
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

address = os.environ.get("GMAIL_ADDRESS", "")
password = os.environ.get("GMAIL_APP_PASSWORD", "")

if not address or not password:
    print("ERROR: GMAIL_ADDRESS or GMAIL_APP_PASSWORD missing in .env")
    sys.exit(1)

print(f"Connecting to imap.gmail.com as {address}...")
try:
    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
        imap.login(address, password)
        typ, data = imap.select("INBOX")
        msg_count = int(data[0]) if typ == "OK" else "?"
        print(f"  OK -- logged in, INBOX has {msg_count} messages total")

        typ, data = imap.search(None, "UNSEEN", 'SUBJECT "[SHELL DEAL]"')
        if typ == "OK":
            unseen = data[0].split()
            print(f"  Matching unread (subject contains '[SHELL DEAL]'): {len(unseen)}")
        imap.logout()
    print("\nCredentials work. You can now run: imap_watcher.py")
except imaplib.IMAP4.error as e:
    print(f"  FAILED: {e}")
    print("\nLikely causes:")
    print("  - App Password is wrong (try regenerating)")
    print("  - 2FA is not enabled on the account")
    print("  - IMAP is disabled in Gmail settings (Settings -> Forwarding and POP/IMAP)")
    sys.exit(1)
