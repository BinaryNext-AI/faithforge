"""Automatic reply detection for the outreach follow-up sequence.

Reads the shared inbox (reusing email_scanner.scan_emails — no new inbox
reader here) and matches the From address of every inbound message against
the contact_email of accounts we are currently "awaiting_reply" on. If a
match arrives after our last outbound send to that account, the lead is
considered to have replied and drops out of the follow-up sequence.

Hard rule: this module NEVER sends anything. It only reads mail (via the
existing scan_emails()) and flips flags/notes on Account rows.
"""
import logging
from datetime import datetime
from email.utils import parseaddr
from typing import Dict

logger = logging.getLogger(__name__)


def _naive_utc(dt):
    """scan_emails() can return tz-aware datetimes (MS Graph, which parses
    ISO-8601 with a UTC offset) while Account.last_contacted_at is always a
    naive UTC datetime (datetime.utcnow()). Normalize before comparing so a
    tz-aware vs tz-naive comparison never raises."""
    if dt is not None and getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def detect_replies(db) -> Dict:
    """Scan the inbox once and flip awaiting_reply/replied_at/stage for any
    account whose contact replied. Returns a summary dict. Commits once, at
    the end, only if something actually changed. Never raises past the
    caller for a scan failure — it just reports checked=0 with an error."""
    from models import Account

    candidates = (
        db.query(Account)
        .filter(
            Account.awaiting_reply.is_(True),
            Account.replied_at.is_(None),
            Account.last_contacted_at.isnot(None),
        )
        .all()
    )
    if not candidates:
        return {"checked": 0, "replied": [], "newly_flagged": 0}

    by_email = {}
    for acc in candidates:
        addr = (acc.contact_email or "").strip().lower()
        if addr:
            by_email[addr] = acc

    if not by_email:
        return {"checked": len(candidates), "replied": [], "newly_flagged": 0}

    from email_scanner import scan_emails
    try:
        inbound = scan_emails()
    except Exception as e:
        logger.exception("[reply_detector] scan_emails failed: %s", e)
        return {"checked": len(candidates), "replied": [], "newly_flagged": 0, "error": str(e)}

    # TODO (header-threading, nice-to-have per spec): also match inbound
    # In-Reply-To/References headers against OutreachEmail.sent_message_id
    # for a more precise signal than address-matching alone. This requires
    # email_scanner.fetch_emails() (IMAP) and the Graph fetch to additionally
    # capture those headers into the returned dict, which they don't today —
    # left as a follow-on since address-matching is the reliable, shippable
    # signal (it doesn't matter whether they hit "reply" or sent fresh).

    now = datetime.utcnow()
    replied_ids = []
    for msg in inbound:
        _, addr = parseaddr(msg.get("email_from") or "")
        addr = (addr or "").strip().lower()
        if not addr or addr not in by_email:
            continue
        acc = by_email[addr]
        if acc.replied_at is not None:
            continue  # already flipped earlier in this same pass

        msg_date = _naive_utc(msg.get("email_date"))
        if not msg_date or not acc.last_contacted_at:
            continue
        if msg_date <= acc.last_contacted_at:
            continue  # inbound message predates our last send — not a reply to it

        acc.awaiting_reply = False
        acc.replied_at = now
        acc.stage = "Replied"
        note = f"Reply detected {now.strftime('%Y-%m-%d %H:%M')} UTC from {addr}"
        acc.notes = f"{acc.notes}\n{note}" if acc.notes else note
        acc.updated_at = now
        replied_ids.append(acc.id)

    if replied_ids:
        db.commit()

    return {"checked": len(candidates), "replied": replied_ids, "newly_flagged": len(replied_ids)}
