"""Load .eml files and extract clean text body (strip HTML if present)."""
from email import policy
from email.parser import BytesParser
from pathlib import Path
from bs4 import BeautifulSoup


def load_eml(path: Path) -> dict:
    with open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    subject = msg.get("Subject", "")
    sender = msg.get("From", "")
    date = msg.get("Date", "")

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

    return {
        "subject": subject,
        "from": sender,
        "date": date,
        "body": body.strip(),
        "filename": path.name,
    }


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(" | ".join(cells))
        table.replace_with("\n".join(rows))
    return soup.get_text(separator="\n", strip=True)
