# Bulk Cold Email Outreach — Build Spec (for the implementing model)

**Feature:** Upload a leads file (Excel/CSV/Google Sheet) → AI generates a personalized
cold email per lead (cost-optimized) → human reviews/edits/approves → send from a dedicated
outreach mailbox. Built on top of the existing `Account` CRM and MS Graph/SMTP send path.

**Status of decisions (locked with the product owner):**
- Leads are stored as **`Account`** rows (reuse existing CRM table + pipeline/dedup/scoring). Do **not** create a parallel leads list.
- Generation supports **both** a fast synchronous mode and the cheap **OpenAI Batch API** mode, chosen **per upload**.
- Approval supports **both** per-email approve/edit **and** bulk "approve all / send all approved."
- Sending uses a **separate, dedicated outreach mailbox (NOT Bernedette's)**. Credentials are **TBD** — the product owner will supply them. Build the config seam now; **default to dry-run**.
- Model: default **`gpt-4o`** (owner said GPT-4o), but make it a setting; note `gpt-4o-mini` is far cheaper if quality allows.

> ⚠️ **Hard safety rules — do not violate:**
> 1. Generating an email NEVER sends it. Send is a separate, explicit, approved-only action.
> 2. Default `OUTREACH_SEND_MODE=dry_run`; live sending requires an explicit settings flip **and** the separate sender creds. In dry-run, all mail routes to a test address with a banner.
> 3. Per-email try/except on send — one failure must not abort the batch.
> 4. Only emails with `status="approved"` may be sent. Never send a `draft`.
> 5. Every outbound email includes a CAN-SPAM footer: FaithForge physical address + a plain-text opt-out line.

---

## 1. Data model — `backend/models.py`

Reuse `Account` for the leads themselves (columns already fit: company_name, segment, website,
location, contact_name, contact_title, contact_email, contact_phone, stage, priority_score,
pain_points, entry_offer, notes, source). Set `source="bulk_upload:<filename>"` on import.

Add two new tables (auto-created by `Base.metadata.create_all` — see §7):

```python
class OutreachBatch(Base):
    __tablename__ = "outreach_batches"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    source_filename = Column(String)
    method = Column(String, default="sync")          # "sync" | "batch_api"
    status = Column(String, default="generating")    # generating | ready | sending | completed | failed
    openai_batch_id = Column(String, nullable=True)   # for Batch API polling
    model_used = Column(String)
    lead_count = Column(Integer, default=0)
    generated_count = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

class OutreachEmail(Base):
    __tablename__ = "outreach_emails"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("outreach_batches.id"), nullable=True, index=True)
    to_email = Column(String)          # snapshot of recipient at generation time (don't re-derive at send)
    subject = Column(String)
    body = Column(Text)
    status = Column(String, default="draft", index=True)  # draft | approved | sending | sent | failed | skipped
    approved = Column(Boolean, default=False)
    edited = Column(Boolean, default=False)   # true once a human edits subject/body
    model_used = Column(String)
    sent_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
```

Add relationships if convenient (`Account.outreach_emails`), but not required.
Keep v1 to **one email per lead** (no multi-step sequence) — simpler and cheaper. The
existing multi-step single-prospect generator in `ai_screener.py` stays as-is for the
one-off `ColdEmail.jsx` page.

---

## 2. Lead import — new `backend/lead_import.py`

- Accept upload of **`.xlsx` / `.xls` / `.csv`** (openpyxl is already a dependency; use it for xlsx, stdlib `csv` for csv).
- **Google Sheets:** accept a share link; convert to the CSV export URL
  (`https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=<gid>`) and fetch with
  `requests` (already a dep). Requires the sheet be link-viewable; if fetch fails, tell the user to export to xlsx/csv and upload.

### Real column schema (from the owner's `FaithForge_Top_25_Maryland_DC_Lead_Sheet.xlsx`)
The reference file is the canonical format. Its columns — map each to an Account field:
| Sheet column | → Account field | Notes |
|---|---|---|
| Priority (1–25) | `priority_score` | invert to 0–100 if desired, or store raw in notes; keep the ordering |
| Name (e.g. "Kevin Marshall, MPM, PMP") | `contact_name` | keep credentials as-is; derive first name for the greeting at generation time |
| Title | `contact_title` | |
| Company / Org | `company_name` | required |
| Location | `location` | |
| Fit for FaithForge | → into `notes` / a context blob | **rich personalization input — feed to the generator** |
| Targeted Gap / Angle | → `pain_points` | **the angle to lead with** |
| How Bernedette Can Help | → `entry_offer` | **the value framing** |
| LinkedIn Profile (URL) | `website` or a new note field | keep the URL; messages double as LinkedIn notes |
| Source URL | notes | |
| Email Status (e.g. "Needs research") | drives sendability (see below) | |
| Email / Contact Notes ("Use LinkedIn first; do not guess email") | notes | |
| First Email / LinkedIn Message | ignore on import (that's the OUTPUT we generate) | can be shown as a prior sample |
| Follow-up Status / Next Step | `stage` (map "Not contacted" → "Not Contacted") | |

Also keep the generic alias fuzzy-matching (company/name/email/title/segment/location/phone/website)
so other spreadsheets still import.

### ⚠️ Leads often have NO email — never guess one
In the reference sheet **all 25 leads have Email Status = "Needs research"** and explicit notes like
*"do not guess email."* Therefore:
- Capture `Email Status` + `Email/Contact Notes`. If there's no real address, leave `contact_email`
  **empty** — do **not** synthesize `first.last@company.com`.
- A lead with no `contact_email` is **generatable but UNSENDABLE**. The generator may still draft the
  message (usable as a LinkedIn note or held until an email is found), but SEND is hard-blocked until a
  real address is added (manually in the UI or a later research step). Surface an **"email needed"**
  badge in the UI and exclude these from any bulk send.

### Two-step import, no surprise writes
- `preview(file) -> {columns, mapping, rows[], dup_flags[], email_missing_count}` — parses, maps, flags
  dups (match on `contact_email` case-insensitive, else `company_name`+`contact_name`) against existing
  Accounts. **No DB writes.**
- `commit(rows, dedupe_strategy) -> {created, updated, skipped, account_ids}` — creates/updates
  Accounts. Default: skip exact-email dups; for emailless rows dedupe on company+name. Set
  `source="bulk_upload:<filename>"`.

---

## 3. Generation — new `backend/outreach_generator.py`

Reuse `knowledge.load_kb()`. Put the final prompt behind a single constant
(`OUTREACH_EMAIL_PROMPT`). **One message per lead.** Output strict JSON `{subject, body}`.

Personalize with the rich per-lead context from the sheet: company_name, contact first name,
contact_title, location, **Fit for FaithForge**, **Targeted Gap / Angle** (`pain_points`),
**How Bernedette Can Help** (`entry_offer`) + FaithForge KB. Trim KB with
`ai_screener.fit_prompt_to_budget`.

### Voice / style — MATCH the owner's reference messages exactly
The reference sheet's "First Email / LinkedIn Message" column is the gold standard. The message is
**dual-purpose (works as a LinkedIn connection note OR a short intro email)**. Rules:
- Open `Hi <FirstName>,` — first name only (strip credentials/last name).
- **3–5 short sentences, ~60–90 words. No subject-line hard-sell.** Warm, peer-to-peer, relationship-first.
- Sentence 1: a specific, genuine observation about *them* — their company, role, focus, or a **local
  Maryland/DC angle** when the location supports it ("we're both in the Odenton/Maryland area").
- Sentence 2: one line on FaithForge Technologies & Consulting — governance, operational structure,
  PMO support, scalable execution (pull the exact angle from *How Bernedette Can Help*).
- Close: a **soft, low-pressure ask** — "I'd enjoy connecting and exchanging perspectives" / "open to
  a coffee sometime." **Never** a demo pitch, discount, or "hop on a call to discuss your needs."
- Signed as **Bernedette Atong, FaithForge Technologies & Consulting** (this is her relationship outreach).
- No fabrication: use only real FaithForge facts; do not invent the prospect's problems beyond the
  sheet's stated angle.
- Provide 3–4 of the sheet's real messages (Kevin, Sanam, Douglas, Jackie rows) as **few-shot
  examples** inside the prompt so tone is locked. When there is no email (LinkedIn-only), the `subject`
  may be empty/short and the body is the connection note.

**Cost strategy — two methods, chosen per upload:**

- **`sync` (immediate):** chunk leads ~10–15 per API call; one `chat.completions` call returns a
  JSON array `[{lead_index, subject, body}, ...]`. ~10× fewer calls than one-per-email. Create
  `OutreachEmail` rows immediately; batch `status="ready"`.
- **`batch_api` (cheapest, async):** build a JSONL (one request per lead, or per small chunk),
  upload via OpenAI Files API, submit to the **Batches API** (`/v1/batches`, 24h window, ~50%
  cheaper). Store `openai_batch_id`, set batch `status="generating"`. A refresh endpoint polls the
  batch; when complete, download output, parse, create `OutreachEmail` rows, set `status="ready"`.
  See OpenAI Batch API docs for the request/response JSONL shape.

Model configurable via `settings.OUTREACH_MODEL` (default `"gpt-4o"`). Record `model_used`.
Guardrails: cap chunk size, cap KB tokens, and **de-dupe before generating** so you never pay to
generate for an already-contacted lead.

---

## 4. Sending — new `backend/outreach_sender.py`

**Sender is now known: `operations@faithforgetech.com`** (owner-specified). The existing Microsoft
Graph app (`MS_CLIENT_ID`/`SECRET`/`TENANT_ID`, `client_credentials`) can **send as** any tenant
mailbox given `Mail.Send` application permission — so the recommended path is to reuse `ms_graph`'s
client and just send *from* `operations@faithforgetech.com` instead of `MS_EMAIL_ADDRESS`, with **no
new credentials**. (Confirm the app has Mail.Send for that mailbox; if not, SMTP is the fallback.)

**Config seam (new settings in `config.py`, overridable via `AppSetting` so the owner can change from
the UI without redeploy):**
```
OUTREACH_SEND_MODE      = "dry_run"   # "dry_run" | "live"   (KEEP dry_run until emails are researched)
OUTREACH_TEST_ADDRESS   = ""          # dry-run recipient; default to NOTIFICATION_EMAIL
OUTREACH_FROM_EMAIL     = "operations@faithforgetech.com"
OUTREACH_FROM_NAME      = "Bernedette Atong — FaithForge"
OUTREACH_TRANSPORT      = "graph"     # "graph" (send-as via existing app) | "smtp"
# SMTP fallback only if Graph send-as isn't permitted:
OUTREACH_SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS
```

`send_outreach_email(email_row, db)`:
1. **Sendability guard:** only proceed if `email_row.status == "approved"` **AND** the linked Account
   has a real `contact_email`. No email → skip with a clear "email needed" result; never guess an address.
2. Build the message. Append a CAN-SPAM footer (FaithForge address from `company_profile.md` +
   plain-text opt-out line). Note: these are warm 1:1 relationship notes, but the footer keeps bulk sends compliant.
3. If `dry_run`: send to `OUTREACH_TEST_ADDRESS` with a `[DRY RUN → would send to <real>]` banner.
   If `live`: send to the Account's `contact_email`.
4. Transport: `graph` → reuse `ms_graph.get_graph_client().send_email(...)` but from
   `OUTREACH_FROM_EMAIL` (add a `from_address` param / a thin `send_email_as` helper). `smtp` fallback
   mirrors the SMTP block in `email_sender.send_packet_email`. Independent of the packet mailbox.
5. On success: `status="sent"`, `sent_at=now`. Advance the Account: stage `Not Contacted → Contacted`,
   `last_contacted_at=now`, `awaiting_reply=True`.
6. On failure: `status="failed"`, record `error`; **do not raise past the batch loop.**
7. Throttle: small sleep (~0.5–1s) between sends.

---

## 5. API endpoints — `backend/main.py` (all behind `require_auth`)

```
POST  /api/outreach/import/preview     multipart file OR {google_sheet_url} -> parsed preview (no writes)
POST  /api/outreach/import/commit      {rows, dedupe} -> {created, updated, skipped, account_ids}
POST  /api/outreach/generate           {account_ids[], method, model?} -> batch (sync: emails ready; batch_api: generating)
GET   /api/outreach/batches            list batches
GET   /api/outreach/batches/{id}       batch + its emails
POST  /api/outreach/batches/{id}/refresh   poll OpenAI batch; ingest results if ready
GET   /api/outreach/emails             ?status=&batch_id=&account_id=  -> list drafts
PATCH /api/outreach/emails/{id}        edit subject/body (sets edited=true, keeps draft) or set approved
POST  /api/outreach/emails/{id}/approve     /unapprove
POST  /api/outreach/emails/bulk-approve     {ids[]}
POST  /api/outreach/emails/{id}/send        single send (approved only)
POST  /api/outreach/send                    {ids[]} -> send all approved; per-email results
GET   /api/outreach/settings                sender config + send mode (AppSetting-backed)
PUT   /api/outreach/settings                update sender config + mode (big warning on live)
```
Add matching Pydantic schemas in `backend/schemas.py`. Log sends to `AuditLog`
(action `"outreach_sent"` / `"outreach_dry_run"`).

---

## 6. Frontend — new `frontend/src/pages/BulkOutreach.jsx` (+ route in `App.jsx`, link in `Sidebar.jsx`)

Wizard-style, reuse existing card/`input`/`btn-primary` classes and `StageBadge` from `Accounts.jsx`.
1. **Upload** — drag/drop xlsx/csv or paste a Google Sheet link → preview table + column mapping +
   dup flags → confirm import.
2. **Generate** — pick imported leads (or "all from this import"); choose **Generate now** (sync) vs
   **Queue cheaply** (Batch API) + model; start. For batch_api, poll `/batches/{id}` for progress.
3. **Review & Approve** — cards/table of drafts (company, contact, subject, body preview); inline
   edit; per-row approve checkbox + **Approve all**; filter by status.
4. **Send** — **Send approved** (bulk) + per-row send. Show a prominent **dry-run banner** whenever
   `OUTREACH_SEND_MODE=dry_run`. Toast per-email results.
- **Settings drawer** — sender account config + send-mode toggle with a loud confirm when switching
  to **live**.
- Add all endpoints to `frontend/src/api.js`.

---

## 7. DB migration note

`database.py::init_db()` calls `Base.metadata.create_all` after importing models. **Add
`OutreachBatch, OutreachEmail` to that import list** in `init_db()` — `create_all` then creates the
new tables on both SQLite and Neon Postgres automatically. No column migration needed (we add tables,
not columns to existing tables). The prod DB is Postgres, so the SQLite-only `_migrate_add_columns`
helper is irrelevant here.

---

## 8. Cost checklist (bake in)

- De-dupe before generating; never generate for already-contacted leads.
- Sync mode: 10–15 leads/call. Batch API: ~50% cheaper, use for large lists.
- KB is already cached (`knowledge.load_kb`); trim with `fit_prompt_to_budget`.
- Expose `OUTREACH_MODEL`; document that `gpt-4o-mini` is ~15× cheaper than `gpt-4o`.
- Record `model_used` + counts per batch so cost is auditable.

## 9. Settled vs. open

**Settled (from the owner + reference sheet):**
- Sender = **`operations@faithforgetech.com`**, signed as Bernedette. Send via existing MS Graph
  send-as (no new creds if Mail.Send app permission covers that mailbox).
- Voice/style = the reference sheet's "First Email / LinkedIn Message" column (warm, brief, soft ask,
  dual-purpose email/LinkedIn). Few-shot from those rows.
- Column schema = the Top-25 lead sheet (see §2 table).
- v1 = single message per lead.

**Open / confirm before go-live:**
- Confirm the Graph app actually has **Mail.Send for `operations@faithforgetech.com`** (else use SMTP).
- **Most leads have no email yet** ("Needs research"). Keep `dry_run` until real addresses are added;
  emailless leads stay unsendable. Decide the email-research workflow (manual entry vs. an enrichment step).
- Opt-out handling: static footer line for v1, or a real unsubscribe link/endpoint later.
- Whether to add the multi-step follow-up sequence later (v1 is single-touch).
