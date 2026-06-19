import imaplib
import email
import email.header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import chardet
import re
from bs4 import BeautifulSoup
from config import settings


def decode_header_value(value: str) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def extract_text_from_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def get_email_body(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body += payload.decode(charset, errors="replace")
                    except Exception:
                        detected = chardet.detect(payload)
                        body += payload.decode(detected.get("encoding") or "utf-8", errors="replace")
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = payload.decode(charset, errors="replace")
                    except Exception:
                        html = payload.decode("utf-8", errors="replace")
                    body = extract_text_from_html(html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                raw = payload.decode(charset, errors="replace")
            except Exception:
                raw = payload.decode("utf-8", errors="replace")
            content_type = msg.get_content_type()
            body = extract_text_from_html(raw) if content_type == "text/html" else raw
    return body.strip()


def quick_keyword_check(subject: str, body: str) -> bool:
    from config import CONTRACT_KEYWORDS, FAITHFORGE_SERVICE_KEYWORDS, MARYLAND_KEYWORDS
    text = (subject + " " + body[:3000]).lower()
    has_contract = any(kw in text for kw in CONTRACT_KEYWORDS)
    has_service = any(kw in text for kw in FAITHFORGE_SERVICE_KEYWORDS)
    has_maryland = any(kw in text for kw in MARYLAND_KEYWORDS)
    return has_contract or (has_service and has_maryland)


def detect_emma_link(body: str) -> Optional[str]:
    from config import EMMA_INDICATORS
    body_lower = body.lower()
    for indicator in EMMA_INDICATORS:
        if indicator in body_lower:
            urls = re.findall(r'https?://[^\s<>"]+emma[^\s<>"]*', body, re.IGNORECASE)
            if urls:
                return urls[0]
            return "EMMA portal (see email)"
    url_matches = re.findall(r'https?://emma\.maryland\.gov[^\s<>"]*', body, re.IGNORECASE)
    if url_matches:
        return url_matches[0]
    return None


class EmailScanner:
    def __init__(self):
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        if not settings.IMAP_HOST or not settings.IMAP_USERNAME:
            raise ValueError("IMAP credentials not configured. Update settings.")
        if settings.IMAP_USE_SSL:
            self.connection = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        else:
            self.connection = imaplib.IMAP4(settings.IMAP_HOST, settings.IMAP_PORT)
        self.connection.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)

    def disconnect(self) -> None:
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def fetch_emails(self, days_back: int = None) -> List[Dict]:
        if not self.connection:
            self.connect()
        days = days_back or settings.IMAP_SCAN_DAYS
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        self.connection.select(settings.IMAP_FOLDER)
        _, message_ids = self.connection.search(None, f'(SINCE "{since_date}")')
        if not message_ids or not message_ids[0]:
            return []
        ids = message_ids[0].split()
        emails = []
        for msg_id in ids[-200:]:  # cap at 200 most recent
            try:
                _, msg_data = self.connection.fetch(msg_id, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = decode_header_value(msg.get("Subject", ""))
                from_addr = decode_header_value(msg.get("From", ""))
                message_id = msg.get("Message-ID", "").strip()
                body = get_email_body(msg)
                date_str = msg.get("Date", "")
                try:
                    email_date = parsedate_to_datetime(date_str)
                except Exception:
                    email_date = datetime.utcnow()
                emma_link = detect_emma_link(body)
                emails.append({
                    "email_id": message_id or f"imap-{msg_id.decode()}",
                    "email_subject": subject,
                    "email_from": from_addr,
                    "email_date": email_date,
                    "email_body": body,
                    "email_body_preview": body[:2000],
                    "has_emma_link": bool(emma_link),
                    "emma_link": emma_link,
                    "passes_keyword_check": quick_keyword_check(subject, body),
                })
            except Exception as e:
                continue
        return emails

    def scan_and_return(self, days_back: int = None) -> List[Dict]:
        try:
            self.connect()
            return self.fetch_emails(days_back)
        finally:
            self.disconnect()


def scan_emails(days_back: int = None) -> List[Dict]:
    """
    Unified entry point. Uses Microsoft Graph API when MS credentials are
    configured, otherwise falls back to IMAP.
    """
    from ms_graph import get_graph_client
    client = get_graph_client()
    if client:
        return client.fetch_emails(days_back or settings.IMAP_SCAN_DAYS)
    return EmailScanner().scan_and_return(days_back)
