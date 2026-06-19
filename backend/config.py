from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./faithforge.db"

    # OpenAI API
    OPENAI_API_KEY: str = ""

    # IMAP (incoming email)
    IMAP_HOST: str = ""
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_FOLDER: str = "INBOX"
    IMAP_USE_SSL: bool = True
    IMAP_SCAN_DAYS: int = 30

    # SMTP (outgoing email)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "FaithForge AI"

    # Microsoft Graph API (replaces IMAP/SMTP for Microsoft 365 / Outlook)
    MS_CLIENT_ID: str = ""
    MS_CLIENT_SECRET: str = ""
    MS_TENANT_ID: str = ""       # tenant ID or "common" for personal accounts
    MS_EMAIL_ADDRESS: str = ""   # mailbox to scan and send from
    MS_AUTH_MODE: str = "client_credentials"  # client_credentials | device_code
    MS_MAIL_FOLDER: str = ""     # folder to scan — blank = all mail, or e.g. "Marketing", "Inbox"

    # Notification destination
    NOTIFICATION_EMAIL: str = ""
    SHAREPOINT_SITE: str = ""
    SHAREPOINT_FOLDER: str = "Documents ready for Review"
    # Reviewer who receives the packet + is granted explicit access to the SharePoint file
    SHAREPOINT_REVIEWER_EMAIL: str = "bernedette.atong@faithforgetech.com"

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB

    # App
    APP_NAME: str = "FaithForge AI Contract Screener"
    DEBUG: bool = False
    APP_PASSWORD: str = "FaithForge2025!"
    # Deployment — comma-separated list of allowed frontend origins (e.g. your Vercel URL)
    ALLOWED_ORIGINS: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

UPLOAD_PATH = os.path.join(os.path.dirname(__file__), settings.UPLOAD_DIR)
os.makedirs(UPLOAD_PATH, exist_ok=True)

# FaithForge keyword lists for pre-screening
CONTRACT_KEYWORDS = [
    # Core procurement types
    "rfp", "rfq", "rfi", "ifb", "solicitation", "bid", "nofo", "sow",
    "request for proposal", "request for quote", "request for information",
    "invitation for bid", "statement of work", "scope of work",
    "contract opportunity", "vendor opportunity", "bid opportunity",
    "proposal request", "procurement", "source sought", "pre-solicitation",
    "notice of funding opportunity", "grant opportunity",
    "cooperative agreement", "task order", "blanket purchase agreement",
    "master agreement", "consulting services", "professional services",
    # Process keywords
    "proposal due date", "pre-bid conference", "addendum",
    "award notice", "intent to bid", "subcontractor opportunity",
    "rfp response", "proposal writing", "proposal submission",
]

FAITHFORGE_SERVICE_KEYWORDS = [
    # Project/Program Management
    "project management", "program management", "pmo", "it project management",
    "business process improvement", "process improvement", "business analysis",
    "vendor management", "contract management", "change management",
    "strategic planning", "administrative support", "operational support",
    # Training & Development
    "training", "workforce development", "professional development",
    "curriculum", "curriculum development", "instructional design",
    "learning management", "certification", "credentialing",
    # Writing & Consulting
    "technical writing", "technical assistance", "grants management",
    "grant writing", "grant administration", "grant management",
    "consulting", "advisory services", "management consulting",
    "compliance", "compliance support",
    # Sectors
    "nonprofit", "non-profit", "faith-based", "community-based",
    "community services", "outreach", "community development",
    "education", "higher education", "school system", "educational services",
    "healthcare", "hospital", "public health", "health services",
    "healthcare training", "healthcare administration",
    # Tech
    "ai", "artificial intelligence", "automation", "digital transformation",
    "technology implementation", "digital services",
    "capacity building", "organizational development",
    "diversity", "equity", "inclusion", "dei", "stem",
]

MARYLAND_KEYWORDS = [
    "emma", "emma.maryland.gov", "maryland marketplace",
    "state of maryland", "maryland", "mdot", "mta", "mde", "sha",
    "maryland department", "county government", "local government",
    "baltimore", "baltimore city", "baltimore county",
    "prince george", "montgomery county", "anne arundel",
    "howard county", "frederick county",
    "public school system", "community college", "university system",
    "health department", "human services",
    "department of education", "department of health",
    "washington dc", "district of columbia",
    "dpscs", "dhcd", "dllr", "mdh", "msde",
]

EMMA_INDICATORS = [
    "emma.maryland.gov",
    "maryland marketplace",
    "emma portal",
    "emma system",
    "register on emma",
    "view on emma",
    "download from emma",
    "emma registration",
]

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"}
