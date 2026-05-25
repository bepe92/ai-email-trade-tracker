# AI Email Trade Tracker

An end-to-end pipeline that watches a shared inbox for trade confirmation emails, uses an LLM to extract structured deal data, and routes every confirmation through a human-in-the-loop web UI before it becomes the source of truth for risk management.

Built as a working prototype for a commodity-trading-desk workflow (oil, gas, refined products). The LLM does the semantic heavy lifting — broker names, products, volumes, prices, dates extracted from emails in wildly different formats — while deterministic Python handles routing, validation, persistence, and audit trail. No regex per broker, no manual copy-paste to Excel.

## The Problem

A typical commodity trading desk closes dozens of broker deals per day. Each broker (Vitol, Trafigura, Mercuria, …) sends a *Deal Confirmation* email — one in plain text, the next in an HTML table, the next as a PDF attachment. The ops team manually retypes those into a master spreadsheet so risk managers can see live exposure. The cost:

- **~3 hours/day** of pure retyping per ops analyst
- **Typos in financial figures** — a misplaced zero on volume × price can mean millions in mis-stated exposure
- **No audit trail** — risk managers see the final number, not who entered it or what the source said

## The Solution

```
┌────────────────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│  Shared inbox      │───▶│  LLM parser │───▶│  Validator   │───▶│  Trader UI     │
│  (IMAP / Graph)    │    │  (Claude)   │    │  (Python)    │    │  (Flask + web) │
│  filter: [SHELL …] │    │             │    │              │    │                │
└────────────────────┘    └─────────────┘    └──────────────┘    └────────────────┘
                                                    │                    │
                                                    ▼                    ▼
                                          ┌──────────────────┐  ┌──────────────────┐
                                          │  Auto-Rejected   │  │  Confirmed deals │
                                          │  (missing/bad    │  │  (after human    │
                                          │   data, closed)  │  │   approval)      │
                                          └──────────────────┘  └──────────────────┘
```

1. **IMAP watcher** polls a dedicated mailbox every 30s, fetches unread messages whose subject contains `[SHELL DEAL]` and ignores everything else.
2. **Claude (Haiku 4.5)** receives the email body with a tight system prompt and returns strict JSON — broker, product, volume in MT, price in USD, unit, trade date, reference. Returns `null` for missing fields rather than guessing.
3. **Validator** checks required fields, types, and date format. If the LLM was unsure or data is incomplete → auto-rejected (no human time wasted). If complete → queued for human review.
4. **Flask web UI** shows each pending deal in a side-by-side view: extracted data on the left, original email on the right, total transaction value (volume × price) prominently displayed for quick scale-check. Trader clicks **Approve** or **Reject** with a reason.
5. **State** is persisted in a single `state.json` with full audit trail — who reviewed, when, what they decided, what the LLM originally extracted.

## Why this design

| Choice | Reason |
|---|---|
| **LLM only where it adds value** | Parsing varied email formats is hard for regex, trivial for an LLM. Everything else is deterministic Python — boring code is reliable code. |
| **`null` over guessing** | The system prompt explicitly forbids guesses. Missing fields auto-reject the deal rather than fabricate. |
| **Human-in-the-loop is the default for valid data, not the exception** | A typo of one zero is millions of USD. LLM is the assistant, the trader is the authority. |
| **Single source of truth (`state.json`)** | Watcher and Flask app both read/write the same file. Atomic writes. Audit trail baked in. |
| **Subject-line filter is unique and explicit** | `[SHELL DEAL]` doesn't collide with bank transfer confirmations or other "potwierdzenie transakcji" emails that might exist in the inbox. |

## Tech stack

- **Python 3.12**
- **Anthropic Claude API** — `claude-haiku-4-5-20251001` for text extraction (cheap, fast, accurate enough)
- **Flask 3** — review UI
- **`imaplib`** — IMAP SSL polling (standard library)
- **`openpyxl`** — optional Excel export (currently unused, kept for export-on-demand)
- **`beautifulsoup4`** — HTML email body normalization

## Quick start

```bash
# 1. Clone
git clone https://github.com/bepe92/ai-email-trade-tracker.git
cd ai-email-trade-tracker

# 2. Virtual env
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install
pip install -r requirements.txt

# 4. Configure secrets — copy template, fill in your own
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# then edit .env with your Anthropic API key + Gmail App Password

# 5. Run batch on the included sample emails to seed state
python src/main.py

# 6. Start the trader review UI (auto-opens at http://localhost:5000)
python src/app.py

# 7. (Optional) Start the live IMAP watcher in another terminal
python src/imap_watcher.py
```

For Gmail: 2FA must be enabled, then generate an [App Password](https://myaccount.google.com/apppasswords) — Google blocks regular passwords for IMAP since 2022.

## Project layout

```
.
├── sample_emails/          # 9 mock Deal Confirmations (3 brokers, 3 formats, 2 broken)
├── src/
│   ├── main.py             # Batch mode — process all .eml files at once
│   ├── imap_watcher.py     # Live mode — poll Gmail every 30s
│   ├── app.py              # Flask trader review UI
│   ├── parser.py           # Claude API call + system prompt
│   ├── validator.py        # Required fields, types, date format checks
│   ├── pipeline.py         # Shared process-one-email logic
│   ├── state_store.py      # JSON-backed deal state with audit trail
│   ├── email_loader.py     # .eml parsing, HTML-to-text normalization
│   └── test_imap_login.py  # One-shot Gmail credential check
├── templates/              # Jinja2 templates for the Flask UI
├── static/style.css        # Styling
├── output/state.json       # (gitignored) Source of truth
└── .env                    # (gitignored) Secrets
```

## What would change for production at scale

This is a working prototype, deliberately demo-grade in a few places. Mapping to a real corporate deployment:

| Demo | Production |
|---|---|
| Personal Gmail + IMAP | Shared M365 mailbox + **Microsoft Graph API** (with webhooks for near-instant trigger) |
| App Password in `.env` | **Azure Key Vault** + Managed Identity — no secrets on disk |
| `state.json` on local disk | **PostgreSQL** — full audit trail, SOX-compliant, queryable |
| Manual `python src/...` | **Container on Azure App Service / Container Apps** — 24/7, auto-restart, Application Insights logs |
| Anthropic public API | **Azure OpenAI** (data stays in tenant) or Anthropic with EU data residency — finance data must not freely egress |
| Single-user Flask | **Flask behind Azure AD/Entra SSO**, role-based access (trader / risk manager / auditor) |
| Excel export on demand | Push approved deals directly to **SharePoint / Power BI / Endur** (or whichever risk system the desk uses) |
| Email body only | Add **Claude Vision** for scanned-PDF attachments (multimodal, no separate OCR layer needed) |

## Roadmap

- [ ] Claude Vision support for PDF attachments (text-layer + image-only PDFs)
- [ ] Broker-name normalization (currently inconsistent casing across LLM runs)
- [ ] Daily Teams/Slack summary digest for the desk lead
- [ ] CSV/Excel export endpoint
- [ ] Multi-user authentication

## License

Personal project for portfolio / interview demonstration. No license granted for production use.
