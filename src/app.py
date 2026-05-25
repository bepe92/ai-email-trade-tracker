"""Trader review UI — Flask app reading/writing the shared state.json."""
import os
import sys
import threading
import webbrowser
from pathlib import Path
from flask import Flask, abort, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).parent))

from state_store import (
    StateStore,
    STATUS_AUTO_REJECTED,
    STATUS_CONFIRMED,
    STATUS_MANUAL_REJECTED,
    STATUS_PENDING,
)

ROOT = Path(__file__).parent.parent
STATE_PATH = ROOT / "output" / "state.json"

DEMO_REVIEWER = os.environ.get("REVIEWER_EMAIL", "trader@shell.com")

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent.parent / "templates"),
    static_folder=str(Path(__file__).parent.parent / "static"),
)


def _state() -> StateStore:
    s = StateStore(STATE_PATH)
    return s


def _deal_total_usd(deal: dict) -> float | None:
    parsed = deal.get("parsed") or {}
    v, p = parsed.get("volume_mt"), parsed.get("price_usd")
    if isinstance(v, (int, float)) and isinstance(p, (int, float)):
        return v * p
    return None


@app.context_processor
def inject_globals():
    counts = _state().counts()
    return {
        "counts": counts,
        "STATUS_PENDING": STATUS_PENDING,
        "STATUS_CONFIRMED": STATUS_CONFIRMED,
        "STATUS_AUTO_REJECTED": STATUS_AUTO_REJECTED,
        "STATUS_MANUAL_REJECTED": STATUS_MANUAL_REJECTED,
        "reviewer": DEMO_REVIEWER,
    }


@app.template_filter("fmt_num")
def fmt_num(value, decimals=0):
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        if decimals == 0:
            return f"{value:,.0f}".replace(",", " ")
        return f"{value:,.{decimals}f}".replace(",", " ")
    return str(value)


@app.template_filter("fmt_money")
def fmt_money(value):
    if value is None:
        return "—"
    return f"${value:,.0f}".replace(",", " ")


@app.route("/")
def index():
    return redirect(url_for("queue", status=STATUS_PENDING))


@app.route("/queue/<status>")
def queue(status):
    valid = {STATUS_PENDING, STATUS_CONFIRMED, STATUS_AUTO_REJECTED, STATUS_MANUAL_REJECTED}
    if status not in valid:
        abort(404)
    s = _state()
    deals = sorted(s.by_status(status), key=lambda d: d["created_at"], reverse=True)
    return render_template("queue.html", deals=deals, active_status=status, deal_total_usd=_deal_total_usd)


@app.route("/deal/<deal_id>")
def deal_detail(deal_id):
    s = _state()
    deal = s.find(deal_id)
    if deal is None:
        abort(404)
    return render_template("deal.html", deal=deal, total_usd=_deal_total_usd(deal))


@app.route("/deal/<deal_id>/approve", methods=["POST"])
def deal_approve(deal_id):
    s = _state()
    if s.approve(deal_id, reviewer=DEMO_REVIEWER) is None:
        abort(400, "Deal not found or not in pending state")
    return redirect(url_for("queue", status=STATUS_PENDING))


@app.route("/deal/<deal_id>/reject", methods=["POST"])
def deal_reject(deal_id):
    s = _state()
    reason = (request.form.get("reason") or "").strip() or "(brak uzasadnienia)"
    if s.reject(deal_id, reviewer=DEMO_REVIEWER, reason=reason) is None:
        abort(400, "Deal not found or not in pending state")
    return redirect(url_for("queue", status=STATUS_PENDING))


PORT = int(os.environ.get("PORT", 5001))


def _open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)
