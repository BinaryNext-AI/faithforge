"""
Microsoft Graph API client for email read/send.

Supports two auth modes:
  - client_credentials: For Microsoft 365 work/school accounts.
    Requires an Azure app registration with Mail.Read + Mail.Send
    *Application* permissions and admin consent. Fully automated.
  - device_code: For personal Outlook.com accounts or when
    client_credentials is not available. User authenticates once
    via a browser code; refresh token is saved to ms_token.json
    for future automated use.
"""

import os
import json
import base64
import requests
import msal
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), "ms_token.json")

# Application permissions (client_credentials flow)
APP_SCOPES = ["https://graph.microsoft.com/.default"]

# Delegated permissions (device_code flow)
DELEGATED_SCOPES = ["Mail.Read", "Mail.Send"]


class MSGraphClient:
    def __init__(self, client_id: str, client_secret: str, tenant_id: str,
                 email_address: str, auth_mode: str = "client_credentials",
                 mail_folder: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.email_address = email_address
        self.auth_mode = auth_mode
        self.mail_folder = mail_folder.strip()
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    # ── Token acquisition ─────────────────────────────────────────────────────

    def _get_token_client_credentials(self) -> str:
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=APP_SCOPES)
        if "access_token" not in result:
            raise RuntimeError(
                f"Microsoft auth failed: {result.get('error_description', result.get('error', 'Unknown error'))}"
            )
        return result["access_token"], result.get("expires_in", 3600)

    def _get_token_device_code(self) -> str:
        """
        Interactive device-code flow. Prints a URL + code for the user to
        visit once. After that the refresh token is cached in ms_token.json
        so future calls are fully automated.
        """
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        cache = msal.SerializableTokenCache()

        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, "r") as f:
                cache.deserialize(f.read())

        app = msal.PublicClientApplication(
            self.client_id,
            authority=authority,
            token_cache=cache,
        )
        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(DELEGATED_SCOPES, account=accounts[0])

        if not result:
            flow = app.initiate_device_flow(scopes=DELEGATED_SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"Device flow init failed: {flow}")
            print("\n" + "="*60)
            print("MICROSOFT ACCOUNT LOGIN REQUIRED")
            print(f"Visit: {flow['verification_uri']}")
            print(f"Code:  {flow['user_code']}")
            print("="*60 + "\n")
            result = app.acquire_token_by_device_flow(flow)

        if cache.has_state_changed:
            with open(TOKEN_CACHE_FILE, "w") as f:
                f.write(cache.serialize())

        if "access_token" not in result:
            raise RuntimeError(
                f"Microsoft auth failed: {result.get('error_description', result.get('error', 'Unknown'))}"
            )
        return result["access_token"], result.get("expires_in", 3600)

    def get_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expiry and now < self._token_expiry:
            return self._access_token
        if self.auth_mode == "client_credentials":
            token, expires_in = self._get_token_client_credentials()
        else:
            token, expires_in = self._get_token_device_code()
        self._access_token = token
        self._token_expiry = now + timedelta(seconds=int(expires_in) - 60)
        return self._access_token

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
        }

    # ── Email reading ─────────────────────────────────────────────────────────

    def _resolve_folder_url(self, folder_name: str) -> str:
        """Return the Graph messages URL for a named folder (or inbox if blank)."""
        user_prefix = (
            f"{GRAPH_BASE}/users/{self.email_address}"
            if self.auth_mode == "client_credentials"
            else f"{GRAPH_BASE}/me"
        )
        if not folder_name:
            return f"{user_prefix}/messages"
        # Well-known folder names that Graph accepts directly
        well_known = {
            "inbox", "drafts", "sentitems", "deleteditems",
            "junkemail", "archive", "outbox",
        }
        if folder_name.lower() in well_known:
            return f"{user_prefix}/mailFolders/{folder_name.lower()}/messages"
        # Custom folder — look up by displayName
        resp = requests.get(
            f"{user_prefix}/mailFolders",
            headers=self._headers(),
            params={"$filter": f"displayName eq '{folder_name}'", "$top": "5"},
            timeout=15,
        )
        resp.raise_for_status()
        folders = resp.json().get("value", [])
        if folders:
            folder_id = folders[0]["id"]
            return f"{user_prefix}/mailFolders/{folder_id}/messages"
        # Fallback to inbox if folder not found
        return f"{user_prefix}/messages"

    def fetch_emails(self, days_back: int = 30, max_count: int = 200) -> List[Dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        base_url = self._resolve_folder_url(self.mail_folder)
        params = {
            "$filter": f"receivedDateTime ge {since}",
            "$select": "id,subject,from,receivedDateTime,body,bodyPreview",
            "$top": "50",
            "$orderby": "receivedDateTime desc",
        }

        emails: List[Dict] = []
        url = base_url

        while url and len(emails) < max_count:
            resp = requests.get(url, headers=self._headers(),
                                params=params if url == base_url else None,
                                timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("value", []):
                raw_body = msg.get("body", {}).get("content", "")
                body_type = msg.get("body", {}).get("contentType", "text")
                body_text = (
                    BeautifulSoup(raw_body, "lxml").get_text(separator=" ", strip=True)
                    if body_type == "html" else raw_body
                )

                from_obj = msg.get("from", {}).get("emailAddress", {})
                from_str = f"{from_obj.get('name', '')} <{from_obj.get('address', '')}>".strip()

                date_str = msg.get("receivedDateTime", "")
                try:
                    email_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    email_date = datetime.now(timezone.utc)

                from email_scanner import quick_keyword_check, detect_emma_link
                emma_link = detect_emma_link(body_text)

                emails.append({
                    "email_id": f"graph-{msg['id']}",
                    "email_subject": msg.get("subject", ""),
                    "email_from": from_str,
                    "email_date": email_date,
                    "email_body": body_text,
                    "email_body_preview": body_text[:2000],
                    "has_emma_link": bool(emma_link),
                    "emma_link": emma_link,
                    "passes_keyword_check": quick_keyword_check(
                        msg.get("subject", ""), body_text
                    ),
                })

            url = data.get("@odata.nextLink")  # None when no more pages

        return emails

    # ── Email sending ─────────────────────────────────────────────────────────

    def send_email(self, to_address, subject: str, html_body: str, bcc: Optional[str] = None) -> bool:
        return self.send_email_with_attachment(to_address, subject, html_body, None, None, bcc=bcc)

    def send_email_with_attachment(
        self, to_address, subject: str, html_body: str,
        pdf_path: Optional[str] = None, opportunity: Optional[dict] = None,
        bcc: Optional[str] = None,
    ) -> bool:
        if self.auth_mode == "client_credentials":
            url = f"{GRAPH_BASE}/users/{self.email_address}/sendMail"
        else:
            url = f"{GRAPH_BASE}/me/sendMail"

        # Accept a single address or a list/comma-separated string
        if isinstance(to_address, str):
            addresses = [a.strip() for a in to_address.split(",") if a.strip()]
        else:
            addresses = [a for a in to_address if a]

        message: dict = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": a}} for a in addresses],
        }
        if bcc:
            bcc_addresses = [a.strip() for a in bcc.split(",") if a.strip()] if isinstance(bcc, str) else [a for a in bcc if a]
            if bcc_addresses:
                message["bccRecipients"] = [{"emailAddress": {"address": a}} for a in bcc_addresses]

        if pdf_path and os.path.exists(pdf_path):
            import base64
            with open(pdf_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode()
            title = (opportunity or {}).get("opportunity_title") or "Packet"
            safe = "".join(c for c in title[:40] if c.isalnum() or c in " -_").strip()
            message["attachments"] = [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": f"FaithForge_Packet_{safe}.pdf",
                "contentType": "application/pdf",
                "contentBytes": pdf_b64,
            }]

        payload = {"message": message, "saveToSentItems": True}
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=60)
        resp.raise_for_status()
        return True


    # ── SharePoint ────────────────────────────────────────────────────────────

    def upload_to_sharepoint(self, site: str, folder: str, filename: str,
                             file_bytes: bytes, reviewer_email: Optional[str] = None) -> Optional[str]:
        """
        Upload a file to a SharePoint document library folder and return a sharing link.
        If reviewer_email is provided, that user is granted explicit access and the
        returned link is the personalised invite link scoped to them.
        """
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}

        # Resolve site ID — Graph API requires hostname:/sites/name format
        site_path = site.replace(".com/sites/", ".com:/sites/", 1)
        site_resp = requests.get(
            f"{GRAPH_BASE}/sites/{site_path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        # Upload file into folder
        upload_url = f"{GRAPH_BASE}/sites/{site_id}/drive/root:/{folder}/{filename}:/content"
        up_resp = requests.put(upload_url, headers=headers, data=file_bytes, timeout=60)
        up_resp.raise_for_status()
        item_id = up_resp.json()["id"]

        json_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Grant the reviewer explicit access (sends them an email from SharePoint too)
        if reviewer_email:
            try:
                invite_resp = requests.post(
                    f"{GRAPH_BASE}/sites/{site_id}/drive/items/{item_id}/invite",
                    headers=json_headers,
                    json={
                        "recipients": [{"email": reviewer_email}],
                        "message": "FaithForge contract packet ready for your review.",
                        "requireSignIn": True,
                        "sendInvitation": True,
                        "roles": ["read"],
                    },
                    timeout=15,
                )
                invite_resp.raise_for_status()
                # The invite response carries a link scoped to the invited user
                for grant in invite_resp.json().get("value", []):
                    web_url = grant.get("link", {}).get("webUrl")
                    if web_url:
                        return web_url
            except Exception:
                pass  # fall back to an organisation link below

        # Create a shareable link (view, organisation scope)
        link_resp = requests.post(
            f"{GRAPH_BASE}/sites/{site_id}/drive/items/{item_id}/createLink",
            headers=json_headers,
            json={"type": "view", "scope": "organization"},
            timeout=15,
        )
        link_resp.raise_for_status()
        return link_resp.json().get("link", {}).get("webUrl")


def get_graph_client() -> Optional[MSGraphClient]:
    """Return a configured client if Graph API credentials are set, else None."""
    from config import settings
    if not (settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET and settings.MS_TENANT_ID and settings.MS_EMAIL_ADDRESS):
        return None
    return MSGraphClient(
        client_id=settings.MS_CLIENT_ID,
        client_secret=settings.MS_CLIENT_SECRET,
        tenant_id=settings.MS_TENANT_ID,
        email_address=settings.MS_EMAIL_ADDRESS,
        auth_mode=settings.MS_AUTH_MODE,
        mail_folder=getattr(settings, "MS_MAIL_FOLDER", ""),
    )
