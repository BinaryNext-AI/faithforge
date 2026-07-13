"""Sends approved bulk-outreach emails from a dedicated mailbox (NOT
Bernedette's personal inbox) — operations@faithforgetech.com by default.

Hard safety rules:
  - Only status == "approved" emails may be sent; drafts are never sent.
  - The linked Account must have a real contact_email — an address is never
    guessed or synthesized.
  - Defaults to dry_run: every send routes to a test address with a banner
    until settings.OUTREACH_SEND_MODE is explicitly flipped to "live".
  - A single send failure never raises past the caller's loop.
"""
import logging
from datetime import datetime
from typing import Any, Dict

from config import settings

logger = logging.getLogger(__name__)

CAN_SPAM_FOOTER_TEXT = (
    "\n\n---\n"
    "FaithForge Technologies & Consulting LLC\n"
    "6865 Deerpath Rd, Suite 101, Elkridge, MD 21075-6255\n"
    "If you'd rather not hear from us again, just reply and let us know."
)

CAN_SPAM_FOOTER_HTML = (
    '<p style="margin-top:24px;padding-top:12px;border-top:1px solid #e2e8f0;'
    'font-size:12px;color:#6b7280;">'
    "FaithForge Technologies &amp; Consulting LLC<br>"
    "6865 Deerpath Rd, Suite 101, Elkridge, MD 21075-6255<br>"
    "If you'd rather not hear from us again, just reply and let us know."
    "</p>"
)


def _graph_client_as(from_email: str):
    """Build an MS Graph client that sends as `from_email` instead of the
    packet-notification mailbox, reusing the same tenant app credentials.
    Only works in client_credentials mode — device_code is tied to a single
    delegated "me" mailbox and cannot send as another address."""
    if not (settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET and settings.MS_TENANT_ID):
        return None
    if settings.MS_AUTH_MODE != "client_credentials":
        return None
    from ms_graph import MSGraphClient
    return MSGraphClient(
        client_id=settings.MS_CLIENT_ID,
        client_secret=settings.MS_CLIENT_SECRET,
        tenant_id=settings.MS_TENANT_ID,
        email_address=from_email,
        auth_mode="client_credentials",
    )


def _send_via_graph(to_address: str, subject: str, html_body: str, bcc: str = "") -> None:
    client = _graph_client_as(settings.OUTREACH_FROM_EMAIL)
    if not client:
        raise RuntimeError(
            "Microsoft Graph is not configured for send-as (need MS_CLIENT_ID/MS_CLIENT_SECRET/"
            "MS_TENANT_ID with MS_AUTH_MODE=client_credentials, and Mail.Send permission for "
            f"{settings.OUTREACH_FROM_EMAIL}). Switch OUTREACH_TRANSPORT to 'smtp' or fix Graph config."
        )
    client.send_email(to_address, subject, html_body, bcc=bcc or None)


def _send_via_smtp(to_address: str, subject: str, html_body: str, text_body: str, bcc: str = "") -> None:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not settings.OUTREACH_SMTP_HOST:
        raise RuntimeError("OUTREACH_SMTP_HOST is not configured.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.OUTREACH_FROM_NAME} <{settings.OUTREACH_FROM_EMAIL}>"
    msg["To"] = to_address
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Bcc is deliberately never added as a header — it's added only to the
    # envelope recipient list below, exactly as the Bcc mechanism requires.
    envelope_recipients = [to_address]
    if bcc:
        envelope_recipients += [a.strip() for a in bcc.split(",") if a.strip()]

    if settings.OUTREACH_SMTP_USE_TLS:
        server = smtplib.SMTP(settings.OUTREACH_SMTP_HOST, settings.OUTREACH_SMTP_PORT)
        server.ehlo()
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(settings.OUTREACH_SMTP_HOST, settings.OUTREACH_SMTP_PORT)
    if settings.OUTREACH_SMTP_USERNAME:
        server.login(settings.OUTREACH_SMTP_USERNAME, settings.OUTREACH_SMTP_PASSWORD)
    server.sendmail(settings.OUTREACH_FROM_EMAIL, envelope_recipients, msg.as_string())
    server.quit()


def send_outreach_email(email_row, account, db) -> Dict[str, Any]:
    """Send one approved OutreachEmail. Returns {ok, dry_run, sent_to, error}.
    Never raises — callers can loop over many of these safely."""
    if email_row.status != "approved":
        return {"ok": False, "error": f"Email status is '{email_row.status}', not 'approved' — refusing to send."}

    real_address = (account.contact_email or "").strip()
    if not real_address:
        email_row.status = "skipped"
        email_row.error = "No verified email address on file for this lead."
        db.commit()
        return {"ok": False, "error": email_row.error}

    dry_run = settings.OUTREACH_SEND_MODE != "live"
    test_address = settings.OUTREACH_TEST_ADDRESS or settings.NOTIFICATION_EMAIL
    send_to = test_address if dry_run else real_address
    if dry_run and not send_to:
        email_row.status = "failed"
        email_row.error = "Dry-run mode has no OUTREACH_TEST_ADDRESS or NOTIFICATION_EMAIL configured."
        db.commit()
        return {"ok": False, "error": email_row.error}

    subject = email_row.subject or "(no subject)"
    body_text = (email_row.body or "") + CAN_SPAM_FOOTER_TEXT
    body_html = (email_row.body or "").replace("\n", "<br>") + CAN_SPAM_FOOTER_HTML

    if dry_run:
        subject = f"[DRY RUN → would send to {real_address}] {subject}"
        body_html = (
            f'<p style="background:#fffbeb;border:1px solid #fcd34d;padding:8px 12px;'
            f'border-radius:6px;color:#92400e;font-size:13px;">DRY RUN &mdash; this would have been '
            f'sent to <strong>{real_address}</strong> ({account.company_name or ""}).</p>'
        ) + body_html

    email_row.status = "sending"
    db.commit()

    bcc = settings.OUTREACH_BCC_EMAIL or ""
    try:
        if settings.OUTREACH_TRANSPORT == "smtp":
            _send_via_smtp(send_to, subject, body_html, body_text, bcc=bcc)
        else:
            _send_via_graph(send_to, subject, body_html, bcc=bcc)
    except Exception as e:
        logger.exception("[outreach] send failed for account %s: %s", account.id, e)
        email_row.status = "failed"
        email_row.error = str(e)
        db.commit()
        return {"ok": False, "error": str(e), "dry_run": dry_run}

    email_row.status = "sent"
    email_row.sent_at = datetime.utcnow()
    email_row.error = None
    db.commit()

    # Advance the CRM pipeline only on a real send — never from a dry run.
    if not dry_run:
        if account.stage == "Not Contacted":
            account.stage = "Contacted"
        account.last_contacted_at = datetime.utcnow()
        account.awaiting_reply = True
        account.updated_at = datetime.utcnow()
        db.commit()

    return {"ok": True, "dry_run": dry_run, "sent_to": send_to}
