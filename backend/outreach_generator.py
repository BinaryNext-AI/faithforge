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

## Make it hard to ignore — persuasion craft (always honest, never manipulative)
- GIVE BEFORE ASKING: every email must contain one thing of genuine standalone value to the reader — a sharp observation they can use, a pattern from their industry, or a concrete offer to share something specific ("happy to send you the 5 governance questions I run on every stalled program — no strings"). The reader should feel they got something even if they never reply.
- PROVE IT'S PERSONAL: at least one detail only someone who actually looked at THEM would know (their title + company + the specific gap in their context). No detail = it reads as blast mail = deleted.
- EARNED CREDIBILITY, one light touch: weave in ONE real credibility marker from the knowledge base (e.g. PgMP-certified, 8+ years across government and healthcare programs) where it supports the insight — never a resume dump, never invented numbers.
- MICRO-ASK CLOSE: end with ONE question so small it can be answered in a single word — "Worth a look?", "Open to swapping notes?", "Should I send it over?". Never two asks, never "book 30 minutes", never a calendar link.
- LOSS-FRAMING allowed, gently: it's fine to note what the status quo quietly costs ("most stalled rollouts lose their best people before they lose the deadline") — but NEVER manufactured urgency, fake deadlines, or pressure tactics.
- NEVER: flattery that isn't grounded in their context, guilt, exaggeration, invented scarcity, or anything Bernedette couldn't say to their face.
- SALES-SPEAK BAN (these instantly mark an email as a pitch and kill replies): "we specialize in", "I leverage", "solutions", "I'm here to help you", "take that crucial step", "unlock", "empower", "fortify", "excellence". Persuasion here comes from a specific true insight plus a tiny ask — never from pitch language. The email must still read 100% like a peer writing personally, not a vendor selling.
- The persuasion craft NEVER overrides the length rule: still 80-110 words, 4-6 sentences. A short pitchy note is worse than no note.
- Sign off as Bernedette Atong, FaithForge Technologies & Consulting.
- Never invent facts about the prospect beyond their given context, and never invent FaithForge statistics or claims not in the knowledge base above.
- Works equally well as a warm intro email or a LinkedIn note.

## FORMATTING — this is a hard requirement, not a style preference
Every "body" must be written as SEPARATE PARAGRAPHS joined by real line breaks (\\n\\n between paragraphs), NEVER one unbroken block of text. Structure every message exactly like this:
1. Greeting line, alone: "Hi <FirstName>,"
2. Opening paragraph (1-2 sentences): the personal observation about them, or the insight-led hook.
3. Body paragraph (2-3 sentences): the specific pain/insight, what it quietly costs in the real world, and where FaithForge fits — grounded in a real FaithForge service from the knowledge base (e.g. Project Rescue's Assessment, Rescue Sprint, or Embedded Leadership) when the lead's context supports a rescue/turnaround angle; otherwise keep it about steady delivery execution.
4. Closing paragraph (1-2 sentences): the concrete no-strings give, then the micro-ask question.
5. Sign-off, on its own final two lines: "Bernedette Atong" then "FaithForge Technologies & Consulting" on the line below it.
A message returned as a single wall of text with no line breaks is WRONG and will be rejected.

## Examples of the required tone AND formatting — warm + sharp, DELIBERATELY VARIED in structure, ALWAYS multi-paragraph (do not copy any one skeleton, but always copy this paragraph shape)

Example 1 — local warmth opening, give-first offer, micro-ask close:
Lead: Kevin Marshall, MPM, PMP — President, Catalyst Consulting & Logistics — Odenton, Maryland
Message:
Hi Kevin,

Fellow Odenton neighbor here — your PMO and consulting background stood out to me right away.

In my experience the hardest part of this work isn't winning the engagement; it's holding governance and accountability together once delivery actually starts. That's exactly the gap a focused rescue assessment is built to close before it becomes a bigger problem.

I keep a short list of the five governance questions I run on every stalled program — happy to send it over, no strings. Want me to share it?

Bernedette Atong
FaithForge Technologies & Consulting

Example 2 — insight-led opening with a light credibility touch:
Lead: Sanam Boroumand — Founder & CEO, Main Digital — Washington DC-Baltimore Area
Message:
Hi Sanam,

The transformation work at Main Digital is impressive.

If it's like most transformation efforts I've led over eight years in government and healthcare programs, the technology is rarely the hard part — keeping teams aligned once delivery starts is. Most stalled rollouts quietly lose their best people before they miss a deadline, and that alignment layer is exactly where FaithForge spends its time.

Open to swapping notes on what's actually working for you?

Bernedette Atong
FaithForge Technologies & Consulting

Example 3 — specific to a high-stakes environment, referencing a real engagement model:
Lead: Douglas Wilson, PMP — Vice President PMO, Maximus — Federal / State Healthcare IT Consulting
Message:
Hi Douglas,

Your PMO leadership across federal and state healthcare IT caught my attention — few environments punish weak governance as fast as regulated healthcare does.

Bringing execution discipline and real PMO structure into exactly those high-stakes settings is the core of what I do. A short, independent assessment is usually enough to surface where the real risk sits before it turns into a missed milestone.

I'd love to send over what that typically looks like — worth a look?

Bernedette Atong
FaithForge Technologies & Consulting

Example 4 — peer-to-peer credibility:
Lead: Jackie Robinson-Burnette — CEO, SES2 LLC — Government Contracting / Retired Federal SES
Message:
Hi Jackie,

Your path from federal senior executive to driving government-contracting growth is genuinely impressive.

Having sat on both sides, you know how often strong programs stall on governance and unclear ownership rather than strategy — which is precisely the gap FaithForge closes for clients in your world.

I'd be glad to send over a short read on what that looks like in practice. Worth a look?

Bernedette Atong
FaithForge Technologies & Consulting

Match this warm-yet-sharp tone, fuller length, AND the exact multi-paragraph shape above (greeting alone, 2-3 body paragraphs, sign-off on its own two lines). Adapt the observation, insight, and angle to each lead's own context, and DELIBERATELY vary the opening and structure from one lead to the next so a batch never reads as a template — but NEVER vary away from the paragraph breaks."""

OUTREACH_BATCH_PROMPT = """Write one outreach message for EACH lead below, in the exact voice described in your system instructions.

Hard requirements for every message (re-read your system instructions before writing):
- FORMATTING IS MANDATORY: the "body" string must contain real \\n\\n line breaks between (1) the "Hi Name," greeting alone on its own line, (2) 2-3 body paragraphs, (3) a sign-off block of "Bernedette Atong" then "FaithForge Technologies & Consulting" on the next line. A single unbroken paragraph with no line breaks is an AUTOMATIC REJECT — match the multi-paragraph shape in the examples exactly.
- EXACTLY 6 sentences across those body paragraphs, structured as: (1) personal opening about them, (2) a sharp insight about their specific pain, (3) how that insight plays out in the real world / what it quietly costs, (4) one light line on where FaithForge fits (ground it in a real FaithForge service — e.g. Project Rescue's Assessment, Rescue Sprint, or Embedded Leadership — when it fits the lead's context), (5) a concrete no-strings give, (6) a micro-ask question. Messages with fewer than 5 sentences are rejected.
- One genuinely useful give (an insight or a concrete no-strings offer to share something specific).
- One micro-ask question at the end, answerable in a word.
- Zero sales-speak ("specialize", "leverage", "solutions", "I'm here to help") — write like a peer, not a vendor.
- Vary each message's opening and structure from the others in this batch — but never vary away from the paragraph-break formatting.

## LEADS
{leads_json}

Return ONLY a valid JSON object with this schema:
{{
  "emails": [
    {{"index": <the lead's index exactly as given>, "subject": "<short, warm subject line, under 8 words, no clickbait>", "body": "<the message, plain text, following the voice rules exactly>"}}
  ]
}}

One entry per lead, in any order, using the exact "index" value given for each lead. Do not skip any lead."""


FOLLOW_UP_ANGLE_BY_STEP = {
    1: (
        "This is follow-up #1. Lead with ONE genuinely new, specific angle or value point they "
        "haven't heard yet — a different way into the same problem than the intro used. Do NOT "
        "open with a content-free bump like \"just wanted to bring this back to the top of your "
        "inbox\" or \"just checking in\" — get straight to the new point in the first sentence."
    ),
    2: (
        "This is follow-up #2. Lead with a short, concrete proof point using ONE REAL result from the "
        "case studies in the knowledge base — the real client name and the real stat, exactly as given "
        "(e.g. an 80% reduction, an 86% cycle-time improvement — whichever real case study is the closest "
        "fit to this lead's world). Pick whichever real case study is the closest fit; if truly none fit, "
        "use a qualitative point about FaithForge's approach instead — NEVER invent a client name, a "
        "percentage, or any stat that is not literally present in the knowledge base. No throat-clearing "
        "opener — get to the proof point immediately."
    ),
    3: (
        "This is follow-up #3, the last nudge before a final close. Make it easier to say yes: shrink "
        "the ask to one quick, low-effort question (e.g. a single yes/no, or offering two concrete "
        "times) rather than repeating the earlier pitch. Keep it the shortest of the three."
    ),
}

FOLLOW_UP_PROMPT = """Each lead below was already sent the intro message shown as "original_message" and has not replied after several days. Write ONE follow-up for EACH lead, in the same warm-but-sharp voice described in your system instructions, with these extra rules:
- FORMATTING IS MANDATORY, same as the intro: real \\n\\n line breaks between the "Hi Name," greeting alone, 1-2 body paragraphs, and a sign-off block of "Bernedette Atong" then "FaithForge Technologies & Consulting" on the next line. Never one unbroken paragraph.
- 3-4 sentences, about 45-70 words — lighter than the intro but still substantial, not a one-liner.
- {step_angle}
- Never guilt-trip, never "did you see my last email?", never manufactured urgency.
- Don't just repeat the intro's wording or angle — this must read as a genuinely different message.
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
    # service_lines.md and voice_reference.md are outreach-only — never added
    # to DEFAULT_KB_FILES, so proposal generation (packet_builder.py's bare
    # load_kb()) never sees them. case_studies.md IS also in DEFAULT_KB_FILES
    # (proposals already use it) — including it here isn't an isolation
    # violation, it just gives outreach real, verified results to cite
    # instead of inventing stats for a follow-up "proof point".
    kb = load_kb("company_profile", "bernedette_bio", "target_market", "service_lines", "voice_reference", "case_studies")
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


def generate_follow_ups(items: List[Dict[str, Any]], model: str = DEFAULT_MODEL, step: int = 1) -> List[Dict[str, Any]]:
    """items: [{"account": Account, "original_body": str}]. `step` (1-3) picks
    the angle for this touch (new value point / proof point / lower-the-ask)
    so the sequence doesn't just re-send the same generic bump each time.
    Returns the same shape as generate_sync: [{account_id, subject, body,
    model_used, error}]."""
    client = _client()
    system = _system_prompt()
    results: List[Dict[str, Any]] = []
    step_angle = FOLLOW_UP_ANGLE_BY_STEP.get(step, FOLLOW_UP_ANGLE_BY_STEP[1])

    for chunk in _chunk(items, CHUNK_SIZE):
        leads = []
        for i, item in enumerate(chunk):
            ctx = _lead_context(item["account"], i)
            ctx["original_message"] = item.get("original_body") or ""
            leads.append(ctx)
        prompt = FOLLOW_UP_PROMPT.format(leads_json=json.dumps(leads, indent=1), step_angle=step_angle)
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


SIGNOFF = "Bernedette Atong\nFaithForge Technologies & Consulting"


def render_breakup_email(account) -> "tuple[str, str]":
    """Sequence step 4 — the final, no-reply-after-3-touches close. Deliberately
    NOT an LLM call: a static, warm, no-pressure template with only
    {first_name}/{company} merged in, so it never drifts in tone or invents
    anything. Same real \\n\\n paragraph breaks and sign-off block as every
    other outreach email."""
    first_name = _first_name(account.contact_name or "")
    company = (account.company_name or "").strip()
    subject = f"Should I close this out, {first_name}?" if first_name != "there" else "Should I close this out?"

    company_line = f" for {company}" if company else ""
    body = (
        f"Hi {first_name},\n\n"
        "Guessing the timing isn't right — totally fine.\n\n"
        f"In case it's useful down the road{company_line}, here's the short version of what FaithForge does: "
        "Project Rescue (an independent Assessment, a hands-on Rescue Sprint, or Embedded Rescue Leadership "
        "for a stalled or at-risk program), plus general delivery and PMO execution support.\n\n"
        "I'll stop following up here — the door's open, just reply if that ever changes.\n\n"
        f"{SIGNOFF}"
    )
    return subject, body


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
