"""Bulk cold-email generation — produces one message per lead, matching
Bernedette's real outreach voice (see the reference FaithForge Top-25
Maryland/DC lead sheet's "First Email / LinkedIn Message" column).

Two generation modes, chosen per upload (see outreach_batches.method):
  - sync:      chunks leads ~10-15 per chat.completions call. Immediate results.
  - batch_api: submits a JSONL job to OpenAI's Batches API (~50% cheaper, async;
               poll_batch() checks/ingests results once the job completes).
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import settings
from knowledge import load_kb

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"
CHUNK_SIZE = 12

OUTREACH_SYSTEM = """You are writing on behalf of Bernedette Atong, Founder & Principal Consultant of FaithForge Technologies & Consulting LLC, a program management and consulting firm in the Maryland/DC area.

{knowledge_base}

## Voice and Style — this is warm relationship-building outreach, NOT a sales pitch
Every message must read like Bernedette personally noticed something specific about this person and wants to connect — not a marketing email. Follow these rules exactly:
- Open with "Hi <FirstName>," using ONLY the first name (strip credentials, suffixes, and last name).
- 3-5 short sentences, about 60-90 words total. No subject-line hard-sell, no bullet points, no "I hope this finds you well."
- Sentence 1: a specific, genuine observation about THEM — their company, role, focus area, or a shared local Maryland/DC connection when the location supports it.
- Sentence 2: one line connecting to FaithForge (governance, operational structure, PMO support, scalable execution) — pull the exact angle from the "how_bernedette_can_help" context given for this lead.
- Close with a soft, low-pressure ask — "I'd enjoy connecting and exchanging perspectives" or "open to a coffee sometime." NEVER a demo pitch, discount, or "let's hop on a call to discuss your needs."
- Sign off as Bernedette Atong, FaithForge Technologies & Consulting.
- Never invent facts about the prospect beyond what's given in their context. Never invent FaithForge statistics or claims not in the knowledge base above.
- This message must work equally well as a LinkedIn connection note or a short intro email — keep it that universal.

## Examples of the exact tone required (real messages Bernedette has sent)

Example 1 — local proximity angle:
Lead: Kevin Marshall, MPM, PMP — President, Catalyst Consulting & Logistics — Odenton, Maryland
Message: "Hi Kevin, I noticed we're both in the Odenton/Maryland area and your background in PMO and consulting immediately stood out to me. At FaithForge Technologies & Consulting, we focus on governance, operational structure, PMO support, and scalable execution. I'd enjoy connecting and seeing if there may be room to exchange ideas or meet for coffee sometime."

Example 2 — transformation angle:
Lead: Sanam Boroumand — Founder & CEO, Main Digital — Washington DC-Baltimore Area
Message: "Hi Sanam, I was impressed by the digital transformation work you're leading at Main Digital. At FaithForge Technologies & Consulting, much of our work focuses on helping organizations strengthen operational alignment, governance, and execution structure around transformation initiatives. I'd value connecting and exchanging perspectives sometime."

Example 3 — regulated/healthcare angle:
Lead: Douglas Wilson, PMP — Vice President PMO, Maximus — Federal / State Healthcare IT Consulting
Message: "Hi Douglas, your healthcare IT and federal/state consulting PMO background stood out to me. At FaithForge Technologies & Consulting, we help organizations strengthen governance, execution discipline, and PMO structure in complex environments. I'd value connecting and learning from your perspective on modern PMO leadership."

Example 4 — executive credibility angle:
Lead: Jackie Robinson-Burnette — CEO, SES2 LLC — Government Contracting / Retired Federal SES
Message: "Hi Jackie, your background as a former federal senior executive and your work supporting government contracting growth really stood out to me. At FaithForge Technologies & Consulting, we help organizations strengthen governance, PMO structure, and execution systems. I'd be honored to connect and learn from your perspective."

Match this exact tone, length, and structure for every lead given — adapt the specific observation and angle to each lead's own context."""

OUTREACH_BATCH_PROMPT = """Write one outreach message for EACH lead below, in the exact voice and structure described in your system instructions.

## LEADS
{leads_json}

Return ONLY a valid JSON object with this schema:
{{
  "emails": [
    {{"index": <the lead's index exactly as given>, "subject": "<short, warm subject line, under 8 words, no clickbait>", "body": "<the message, plain text, following the voice rules exactly>"}}
  ]
}}

One entry per lead, in any order, using the exact "index" value given for each lead. Do not skip any lead."""


def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _first_name(full_name: str) -> str:
    if not full_name:
        return "there"
    name = full_name.split(",")[0].strip()
    parts = name.split()
    return parts[0] if parts else full_name.strip()


def _lead_context(account, index: int) -> Dict[str, Any]:
    return {
        "index": index,
        "first_name": _first_name(account.contact_name or ""),
        "full_name": account.contact_name or "",
        "title": account.contact_title or "",
        "company": account.company_name or "",
        "location": account.location or "",
        "targeted_gap_angle": account.pain_points or "",
        "how_bernedette_can_help": account.entry_offer or "",
    }


def _system_prompt() -> str:
    kb = load_kb("company_profile", "bernedette_bio", "target_market")
    return OUTREACH_SYSTEM.format(knowledge_base=kb)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None


def _chunk(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


# ── Sync mode ────────────────────────────────────────────────────────────────

def generate_sync(accounts: List, model: str = DEFAULT_MODEL) -> List[Dict[str, Any]]:
    """Generate one email per account, chunked into a handful of API calls.
    Returns a list of {account_id, subject, body, model_used, error}."""
    client = _client()
    system = _system_prompt()
    results: List[Dict[str, Any]] = []

    for chunk in _chunk(accounts, CHUNK_SIZE):
        leads = [_lead_context(acc, i) for i, acc in enumerate(chunk)]
        prompt = OUTREACH_BATCH_PROMPT.format(leads_json=json.dumps(leads, indent=1))
        chunk_error = None
        by_index: Dict[int, dict] = {}
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=350 * len(chunk) + 200,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content or ""
            parsed = _extract_json(raw) or {}
            by_index = {int(e["index"]): e for e in parsed.get("emails", []) if "index" in e}
        except Exception as e:
            logger.exception("[outreach] sync chunk failed: %s", e)
            chunk_error = str(e)

        for i, acc in enumerate(chunk):
            entry = by_index.get(i)
            if entry:
                results.append({
                    "account_id": acc.id,
                    "subject": (entry.get("subject") or "").strip(),
                    "body": (entry.get("body") or "").strip(),
                    "model_used": model,
                    "error": None,
                })
            else:
                results.append({
                    "account_id": acc.id,
                    "subject": "",
                    "body": "",
                    "model_used": model,
                    "error": chunk_error or "Model did not return this lead — retry generation.",
                })
    return results


# ── Batch API mode (cheap, async) ────────────────────────────────────────────

def build_batch_jsonl(accounts: List, model: str = DEFAULT_MODEL) -> bytes:
    """One request per lead, using a stable custom_id of 'account-<id>' so
    results map back to the right Account when the job completes."""
    system = _system_prompt()
    lines = []
    for acc in accounts:
        lead = _lead_context(acc, 0)
        prompt = OUTREACH_BATCH_PROMPT.format(leads_json=json.dumps([lead], indent=1))
        body = {
            "custom_id": f"account-{acc.id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        }
        lines.append(json.dumps(body))
    return ("\n".join(lines) + "\n").encode("utf-8")


def submit_batch(accounts: List, model: str = DEFAULT_MODEL) -> str:
    """Upload the JSONL + create the batch job. Returns the OpenAI batch id."""
    client = _client()
    jsonl_bytes = build_batch_jsonl(accounts, model=model)
    file_obj = client.files.create(file=("outreach_batch.jsonl", jsonl_bytes), purpose="batch")
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return batch.id


def poll_batch(openai_batch_id: str) -> Dict[str, Any]:
    """Check batch status. results is populated only once the batch has
    completed and its output file has been downloaded and parsed."""
    client = _client()
    batch = client.batches.retrieve(openai_batch_id)
    status = batch.status  # validating|in_progress|finalizing|completed|failed|expired|cancelled

    if status != "completed" or not batch.output_file_id:
        return {"status": status, "results": None, "error": getattr(batch, "errors", None)}

    file_content = client.files.content(batch.output_file_id)
    results = []
    for line in file_content.text.strip().split("\n"):
        if not line.strip():
            continue
        row = json.loads(line)
        custom_id = row.get("custom_id", "")
        account_id = None
        if custom_id.startswith("account-"):
            try:
                account_id = int(custom_id.split("-", 1)[1])
            except ValueError:
                pass

        response = row.get("response") or {}
        error = row.get("error")
        subject, body, parsed_error = "", "", None
        if error:
            parsed_error = str(error)
        else:
            try:
                content = response["body"]["choices"][0]["message"]["content"]
                parsed = _extract_json(content) or {}
                emails = parsed.get("emails") or []
                if emails:
                    subject = (emails[0].get("subject") or "").strip()
                    body = (emails[0].get("body") or "").strip()
                else:
                    parsed_error = "Model returned no email for this lead."
            except Exception as e:
                parsed_error = f"Could not parse batch result: {e}"

        results.append({
            "account_id": account_id,
            "subject": subject,
            "body": body,
            "error": parsed_error,
        })

    return {"status": status, "results": results, "error": None}
