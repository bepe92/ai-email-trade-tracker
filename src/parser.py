"""LLM-based Deal Confirmation parser using Claude Haiku 4.5."""
import json
import os
from anthropic import Anthropic

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """Jesteś precyzyjnym asystentem danych w Shell Trading. \
Przeczytaj poniższą treść maila Deal Confirmation i wyciągnij z niej wyłącznie następujące dane:

- broker: nazwa kontrahenta wysyłającego potwierdzenie (np. "Vitol Trading S.A.")
- product: nazwa produktu (np. "Brent Crude Oil", "Natural Gas", "Jet Fuel A1")
- volume_mt: wolumen w tonach metrycznych jako liczba (bez jednostki, bez przecinków)
- price_usd: cena jednostkowa w USD jako liczba (bez waluty, bez jednostki)
- price_unit: jednostka ceny (np. "per barrel", "per MT", "per MMBtu")
- trade_date: data transakcji w formacie YYYY-MM-DD
- reference: numer referencyjny transakcji (np. "VT-2026-04821")

Zwróć wynik w czystym formacie JSON, bez żadnego komentarza, bez markdown, bez ```.
Jeśli któreś pole jest niedostępne lub niejednoznaczne (np. "TBD", "pending", brak), \
ustaw jego wartość na null. NIE zgaduj wartości.

Przykład poprawnej odpowiedzi:
{"broker": "Vitol Trading S.A.", "product": "Brent Crude Oil", "volume_mt": 45000, \
"price_usd": 82.45, "price_unit": "per barrel", "trade_date": "2026-05-25", \
"reference": "VT-2026-04821"}"""


def parse_email(email_body: str, client: Anthropic | None = None) -> dict:
    if client is None:
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": email_body}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
