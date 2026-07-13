"""Looks up a verified work email for a lead via Apollo.io's people-match API.

Only ever *suggests* an address — the caller (and ultimately the user in the
UI) decides whether to save it onto the Account. Never writes to the DB.

Requires APOLLO_API_KEY (Apollo dashboard → Settings → Integrations → API).
Each successful match consumes Apollo credits.
"""
import logging
import re
from typing import Any, Dict

import requests

from config import settings

logger = logging.getLogger(__name__)

MATCH_URL = "https://api.apollo.io/api/v1/people/match"

# Apollo returns this placeholder when the account has no email credits left
_LOCKED_RE = re.compile(r"email_not_unlocked", re.IGNORECASE)


def _split_name(full_name: str) -> tuple:
    """'Kevin Marshall, MPM, PMP' -> ('Kevin', 'Marshall'). Credentials after a
    comma are stripped; middle names fold into the last name."""
    name = (full_name or "").split(",")[0].strip()
    parts = name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _domain_from_website(website: str) -> str:
    if not website:
        return ""
    d = re.sub(r"^https?://", "", website.strip(), flags=re.IGNORECASE)
    d = d.split("/")[0].strip()
    return d.removeprefix("www.")


def find_email(account) -> Dict[str, Any]:
    """Returns {ok, email, email_status, person_title, linkedin_url, error}.
    ok=True with email=None means Apollo answered but has no address for them."""
    api_key = (settings.APOLLO_API_KEY or "").strip()
    if not api_key:
        return {"ok": False, "error": "Apollo API key is not configured. Add it in Settings → APOLLO_API_KEY (from apollo.io → Settings → API)."}

    first, last = _split_name(account.contact_name or "")
    if not first or not (account.company_name or "").strip():
        return {"ok": False, "error": "Need at least a contact first name and company name to look up an email."}

    payload = {
        "first_name": first,
        "last_name": last,
        "organization_name": account.company_name.strip(),
        "reveal_personal_emails": False,
    }
    domain = _domain_from_website(account.website or "")
    if domain:
        payload["domain"] = domain

    try:
        resp = requests.post(
            MATCH_URL,
            json=payload,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"Could not reach Apollo: {e}"}

    if resp.status_code == 401:
        return {"ok": False, "error": "Apollo rejected the API key — check APOLLO_API_KEY in Settings."}
    if resp.status_code == 402 or resp.status_code == 403:
        return {"ok": False, "error": "Apollo says this plan/key has no access to email lookups (upgrade or check API permissions)."}
    if resp.status_code == 429:
        return {"ok": False, "error": "Apollo rate limit hit — wait a minute and try again."}
    if resp.status_code >= 400:
        return {"ok": False, "error": f"Apollo error {resp.status_code}: {resp.text[:200]}"}

    person = (resp.json() or {}).get("person") or {}
    if not person:
        return {"ok": True, "email": None, "error": None,
                "message": "Apollo could not find this person — try adding their company website to the account."}

    email = (person.get("email") or "").strip()
    if not email or _LOCKED_RE.search(email):
        return {"ok": True, "email": None, "error": None,
                "message": "Apollo found the person but has no unlocked email (out of credits, or none on file)."}

    return {
        "ok": True,
        "email": email,
        "email_status": person.get("email_status"),  # e.g. "verified"
        "person_title": person.get("title"),
        "linkedin_url": person.get("linkedin_url"),
        "error": None,
    }
