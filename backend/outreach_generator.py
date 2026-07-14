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

## Voice and Style — warm but sharp; a senior operator reaching out personally, NOT a marketing email
Every message should feel like Bernedette personally noticed this person AND has a specific, credible point of view worth their time. Blend genuine warmth with a confident, insight-led edge. Follow these rules:
- Open with "Hi <FirstName>," using ONLY the first name (strip credentials, suffixes, last name). If no real first name is given, use "Hi there,".
- 4-6 sentences, about 80-110 words. Substantial enough to say something real — never a one-line throwaway, never padded filler either.
- VARY the structure across leads — do NOT reuse one skeleton. Some emails open with a genuine, specific observation about them; others open with a sharp, credible insight about their industry or role that proves you understand their world. Mix warm openings and insight-led openings across a batch.
- Weave the FaithForge angle in naturally and DIFFERENTLY every time. NEVER mechanically start a sentence with "At FaithForge Technologies & Consulting, we..." — the full firm name belongs in the sign-off. Inside the body refer to it lightly ("FaithForge", "what I do", "the work I do") and tie it to a REAL, specific problem this person likely faces, pulled from their context.
- Name a concrete, believable dynamic or pain in their world. BAN vague corporate filler like "align teams and ensure deliverables", "drive synergies", "strengthen operational alignment". Say something a real practitioner would say.
- Close with a warm, low-pressure ask — connecting, trading notes, comparing perspectives, coffee. NEVER a demo pitch, discount, or "let's hop on a call to discuss your needs."
- Sign off as Bernedette Atong, FaithForge Technologies & Consulting.
- Never invent facts about the prospect beyond their given context, and never invent FaithForge statistics or claims not in the knowledge base above.
- Works equally well as a warm intro email or a LinkedIn note.

## Examples of the required tone — warm + sharp, and DELIBERATELY VARIED in structure (do not copy any one skeleton)

Example 1 — local warmth opening into a sharp insight:
Lead: Kevin Marshall, MPM, PMP — President, Catalyst Consulting & Logistics — Odenton, Maryland
Message: "Hi Kevin, fellow Odenton neighbor here — your PMO and consulting background stood out to me right away. In my experience the hardest part of this work isn't winning the engagement; it's holding governance and accountability together once delivery actually starts. That's the exact problem I built FaithForge to solve. I'd genuinely enjoy trading notes over coffee sometime and hearing how you approach it."

Example 2 — insight-led opening (no compliment first):
Lead: Sanam Boroumand — Founder & CEO, Main Digital — Washington DC-Baltimore Area
Message: "Hi Sanam, the transformation work at Main Digital is impressive — and if it's like most transformation efforts I see, the technology is rarely the hard part; keeping teams aligned and execution disciplined is. That alignment layer is where FaithForge spends its time. I'd value a conversation and your take on what's actually been working for you."

Example 3 — specific to a high-stakes environment:
Lead: Douglas Wilson, PMP — Vice President PMO, Maximus — Federal / State Healthcare IT Consulting
Message: "Hi Douglas, your PMO leadership across federal and state healthcare IT caught my attention — few environments punish weak governance as fast as regulated healthcare does. Bringing execution discipline and real PMO structure into exactly those high-stakes settings is the core of what I do at FaithForge. I'd love to connect and hear how you're thinking about modern PMO leadership."

Example 4 — peer-to-peer credibility:
Lead: Jackie Robinson-Burnette — CEO, SES2 LLC — Government Contracting / Retired Federal SES
Message: "Hi Jackie, your path from federal senior executive to driving government-contracting growth is genuinely impressive. Having sat on both sides, you know how often strong programs stall on governance and unclear ownership rather than strategy — which is precisely the gap FaithForge closes. I'd be honored to connect and learn from your perspective on where the market is heading."

Match this warm-yet-sharp tone and fuller length. Adapt the observation, insight, and angle to each lead's own context, and DELIBERATELY vary the opening and structure from one lead to the next so a batch never reads as a template."""

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


FOLLOW_UP_PROMPT = """Each lead below was already sent the intro message shown as "original_message" and has not replied after several days. Write ONE follow-up for EACH lead, in the same warm-but-sharp voice described in your system instructions, with these extra rules:
- 3-4 sentences, about 45-70 words — lighter than the intro but still substantial, not a one-liner.
- Gently float the earlier note back up ("just wanted to bring this back to the top of your inbox") — never guilt-trip, never "did you see my last email?", never manufactured urgency.
- Add ONE genuinely new, specific reason to connect or a small relevant insight — don't just repeat the intro.
- Same warm low-pressure close and the Bernedette Atong, FaithForge Technologies & Consulting sign-off.

## LEADS
{leads_json}

Return ONLY a valid JSON object with this schema:
{{
  "emails": [
    {{"index": <the lead's index exactly as given>, "subject": "<short, warm subject, under 8 words>", "body": "<the follow-up, plain text>"}}
  ]
}}

One entry per lead, using the exact "index" value given. Do not skip any lead."""


def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _first_name(full_name: str) -> str:
    """Best real-looking first name, else 'there'. Skips ID-like or single-
    letter tokens so a value like 'L 230601' yields 'there', not 'L'."""
    if not full_name:
        return "there"
    name = full_name.split(",")[0].strip()
    for token in name.split():
        cleaned = token.replace("-", "").replace("'", "")
        if len(cleaned) >= 2 and cleaned.isalpha():
            return token
    return "there"


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


def generate_follow_ups(items: List[Dict[str, Any]], model: str = DEFAULT_MODEL) -> List[Dict[str, Any]]:
    """items: [{"account": Account, "original_body": str}]. Returns the same
    shape as generate_sync: [{account_id, subject, body, model_used, error}]."""
    client = _client()
    system = _system_prompt()
    results: List[Dict[str, Any]] = []

    for chunk in _chunk(items, CHUNK_SIZE):
        leads = []
        for i, item in enumerate(chunk):
            ctx = _lead_context(item["account"], i)
            ctx["original_message"] = item.get("original_body") or ""
            leads.append(ctx)
        prompt = FOLLOW_UP_PROMPT.format(leads_json=json.dumps(leads, indent=1))
        chunk_error = None
        by_index: Dict[int, dict] = {}
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=250 * len(chunk) + 200,
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
            logger.exception("[outreach] follow-up chunk failed: %s", e)
            chunk_error = str(e)

        for i, item in enumerate(chunk):
            entry = by_index.get(i)
            results.append({
                "account_id": item["account"].id,
                "subject": (entry.get("subject") or "").strip() if entry else "",
                "body": (entry.get("body") or "").strip() if entry else "",
                "model_used": model,
                "error": None if entry else (chunk_error or "Model did not return this lead — retry generation."),
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
