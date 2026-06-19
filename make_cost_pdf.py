"""Generate FaithForge AI API Cost Proposal PDF using fpdf2."""
from fpdf import FPDF

def _s(text):
    """Strip non-latin-1 characters."""
    return "".join(c if ord(c) < 256 else "-" for c in str(text).replace("-", " - ").replace("–", "-").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))

L = 18; R = 18; PW = 210; CW = PW - L - R  # A4, content width 174mm

NAVY  = (26,  54,  93)
BLUE  = (59, 130, 246)
LBLUE = (239, 246, 255)
GREEN = (5,  150, 105)
LGRN  = (209, 250, 229)
RED   = (220,  38,  38)
LRED  = (254, 226, 226)
GRAY  = (107, 114, 128)
DGRAY = (55,  65,  81)
WHITE = (255, 255, 255)
BLACK = (0,   0,   0)
ROW1  = (248, 250, 252)


def s(pdf): pdf.set_x(L)

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica","I",8); self.set_text_color(*GRAY); s(self)
        self.cell(CW,5,"FaithForge Technologies & Consulting LLC  |  INTERNAL - BUDGET APPROVAL",ln=True)
        self.set_text_color(*BLACK); self.ln(1)
    def footer(self):
        self.set_y(-12); self.set_font("Helvetica","",8)
        self.set_text_color(*GRAY)
        self.cell(0,6,f"Page {self.page_no()}  |  FaithForge AI API Cost Proposal  |  June 2026",align="C")
        self.set_text_color(*BLACK)


def h1(pdf, text):
    pdf.ln(4); s(pdf)
    pdf.set_fill_color(*LBLUE); pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica","B",14)
    pdf.multi_cell(CW,9,text,fill=True); s(pdf)
    pdf.set_text_color(*BLACK); pdf.ln(1)

def h2(pdf, text):
    pdf.ln(5)
    pdf.set_font("Helvetica","B",10); pdf.set_text_color(*NAVY); s(pdf)
    pdf.multi_cell(CW,6,text); s(pdf)
    pdf.set_draw_color(*BLUE); pdf.set_line_width(0.5)
    pdf.line(L, pdf.get_y(), L+CW, pdf.get_y())
    pdf.set_text_color(*BLACK); s(pdf); pdf.ln(3)

def h3(pdf, text):
    pdf.ln(2); pdf.set_font("Helvetica","B",9); pdf.set_text_color(*DGRAY); s(pdf)
    pdf.multi_cell(CW,5,text); s(pdf); pdf.set_text_color(*BLACK)

def para(pdf, text, size=9.5):
    pdf.set_font("Helvetica","",size); pdf.set_text_color(*DGRAY); s(pdf)
    pdf.multi_cell(CW,5.5,text); s(pdf); pdf.ln(1)

def bullet(pdf, text):
    pdf.set_font("Helvetica","",9); pdf.set_text_color(*DGRAY)
    pdf.set_x(L+4); pdf.multi_cell(CW-4,5,"-  "+text); s(pdf)

def hr(pdf, color=GRAY):
    pdf.set_draw_color(*color); pdf.set_line_width(0.2); s(pdf)
    pdf.line(L, pdf.get_y(), L+CW, pdf.get_y()); s(pdf); pdf.ln(2)


def highlight_box(pdf, big_text, label):
    pdf.ln(3); s(pdf)
    pdf.set_fill_color(*LBLUE)
    by = pdf.get_y()
    pdf.rect(L, by, CW, 18, "F")
    pdf.set_xy(L+4, by+2)
    pdf.set_font("Helvetica","B",22); pdf.set_text_color(*NAVY)
    pdf.cell(80,8,big_text)
    pdf.set_xy(L+4, by+11)
    pdf.set_font("Helvetica","",8); pdf.set_text_color(*GRAY)
    pdf.cell(CW-8,5,label)
    pdf.set_xy(L, by+18); pdf.ln(4)
    pdf.set_text_color(*BLACK)


def two_cards(pdf, left_title, left_items, right_title, right_items):
    pdf.ln(2)
    col = (CW-4)/2
    ly = pdf.get_y()

    # measure heights
    pdf.set_font("Helvetica","",8.5)
    def text_h(items, w):
        h = 7
        for it in items:
            lines = max(1, int(pdf.get_string_width("-  "+it) / (w-6)) + 1)
            h += lines * 4.8
        return h + 4

    lh = text_h(left_items,  col)
    rh = text_h(right_items, col)
    bh = max(lh, rh)

    if pdf.get_y() + bh > pdf.h - 22:
        pdf.add_page(); ly = pdf.get_y()

    # left card (red)
    pdf.set_fill_color(*LRED)
    pdf.rect(L, ly, col, bh, "F")
    pdf.set_draw_color(*RED); pdf.set_line_width(0.4)
    pdf.line(L, ly, L, ly+bh)
    pdf.set_xy(L+3, ly+2)
    pdf.set_font("Helvetica","B",8); pdf.set_text_color(*RED)
    pdf.cell(col-4,5,left_title,ln=True)
    for it in left_items:
        pdf.set_x(L+3); pdf.set_font("Helvetica","",8); pdf.set_text_color(*DGRAY)
        pdf.multi_cell(col-6,4.8,"-  "+it)

    # right card (green)
    rx = L+col+4
    pdf.set_fill_color(*LGRN)
    pdf.rect(rx, ly, col, bh, "F")
    pdf.set_draw_color(*GREEN); pdf.set_line_width(0.4)
    pdf.line(rx, ly, rx, ly+bh)
    pdf.set_xy(rx+3, ly+2)
    pdf.set_font("Helvetica","B",8); pdf.set_text_color(*GREEN)
    pdf.cell(col-4,5,right_title,ln=True)
    for it in right_items:
        pdf.set_x(rx+3); pdf.set_font("Helvetica","",8); pdf.set_text_color(*DGRAY)
        pdf.multi_cell(col-6,4.8,"-  "+it)

    pdf.set_xy(L, ly+bh+4); pdf.set_text_color(*BLACK)


def table(pdf, headers, rows, col_ws, footer_row=None, winner_row=None):
    row_h = 6.5; pad = 2
    if pdf.get_y() + row_h*(len(rows)+2) > pdf.h - 22:
        pdf.add_page()
    s(pdf)
    # header
    pdf.set_fill_color(*NAVY); pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica","B",8)
    x0 = L
    for i,(h,w) in enumerate(zip(headers,col_ws)):
        pdf.set_xy(x0, pdf.get_y())
        pdf.cell(w, row_h, h, border=0, fill=True)
        x0 += w
    pdf.ln(row_h); s(pdf)
    # rows
    for ri,row in enumerate(rows):
        y0 = pdf.get_y()
        if y0 + row_h > pdf.h - 22: pdf.add_page(); y0 = pdf.get_y()
        is_winner = winner_row is not None and ri == winner_row
        fill_c = LGRN if is_winner else (ROW1 if ri%2==0 else WHITE)
        text_c = (5,150,105) if is_winner else DGRAY
        pdf.set_fill_color(*fill_c)
        x0 = L
        for ci,(cell,w) in enumerate(zip(row,col_ws)):
            pdf.set_xy(x0, y0)
            is_bold = ci==0 or (ci==len(row)-1 and ri==len(rows)-1)
            pdf.set_font("Helvetica","B" if is_winner or (ci==0) else "",8)
            pdf.set_text_color(*(GREEN if is_winner else (NAVY if ci==0 else DGRAY)))
            pdf.cell(w, row_h, str(cell), border=0, fill=True)
            x0 += w
        pdf.ln(row_h); s(pdf)
    # footer
    if footer_row:
        y0 = pdf.get_y()
        pdf.set_fill_color(*NAVY); x0 = L
        for cell,w in zip(footer_row,col_ws):
            pdf.set_xy(x0,y0)
            pdf.set_font("Helvetica","B",8); pdf.set_text_color(*WHITE)
            pdf.cell(w,row_h,str(cell),border=0,fill=True)
            x0 += w
        pdf.ln(row_h); s(pdf)
    pdf.set_text_color(*BLACK); pdf.ln(2)


def roi_box(pdf):
    pdf.ln(3); s(pdf)
    bx = L; by = pdf.get_y(); bh = 36
    if by + bh > pdf.h - 22: pdf.add_page(); by = pdf.get_y()
    pdf.set_fill_color(*NAVY); pdf.rect(bx, by, CW, bh, "F")
    pdf.set_xy(bx+4, by+3)
    pdf.set_font("Helvetica","B",8); pdf.set_text_color(147,197,253)
    pdf.cell(CW-8,5,"RETURN ON INVESTMENT CONTEXT",ln=True)
    # 3 stat boxes
    stats = [("$2.62","Monthly API cost"),("$31.41","Annual API cost"),("1 contract","Covers 10+ years of API")]
    for i,(val,lbl) in enumerate(stats):
        sx = bx + 4 + i*(CW//3)
        pdf.set_xy(sx, by+10); pdf.set_font("Helvetica","B",16); pdf.set_text_color(*WHITE)
        pdf.cell(CW//3,8,val)
        pdf.set_xy(sx, by+19); pdf.set_font("Helvetica","",7.5); pdf.set_text_color(147,197,253)
        pdf.cell(CW//3,5,lbl)
    pdf.set_xy(bx+4, by+26)
    pdf.set_font("Helvetica","I",8); pdf.set_text_color(191,219,254)
    pdf.multi_cell(CW-8,4.5,
        "A single awarded contract (typically $50,000-$500,000 for government PMO engagements) covers the "
        "entire annual API cost by a factor of 1,500x-15,000x. The $31.41 annual cost is negligible relative "
        "to the business development value delivered.")
    pdf.set_xy(L, by+bh+4); pdf.set_text_color(*BLACK)


# ── BUILD PDF ─────────────────────────────────────────────────────────────────
pdf = PDF(); pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(L,14,R); pdf.add_page()

# ── TITLE BLOCK ───────────────────────────────────────────────────────────────
pdf.set_font("Helvetica","B",18); pdf.set_text_color(*NAVY); s(pdf)
pdf.multi_cell(CW,10,"FaithForge Technologies & Consulting LLC"); s(pdf)
pdf.set_font("Helvetica","B",14); pdf.set_text_color(*DGRAY); s(pdf)
pdf.multi_cell(CW,7,"AI API Cost Proposal - GPT-4o-mini"); s(pdf)
pdf.set_font("Helvetica","",9); pdf.set_text_color(*GRAY); s(pdf)
pdf.multi_cell(CW,5,"Monthly operating cost breakdown for the FaithForge Contract Opportunity Screener"); s(pdf)
pdf.ln(1)
pdf.set_font("Helvetica","",9); pdf.set_text_color(*GRAY); s(pdf)
pdf.cell(CW/2,5,"Date: June 16, 2026")
pdf.cell(CW/2,5,"Classification: Internal - Budget Approval",ln=True); s(pdf)
pdf.set_draw_color(*NAVY); pdf.set_line_width(1.0)
pdf.line(L, pdf.get_y()+2, L+CW, pdf.get_y()+2); pdf.ln(6); s(pdf)
pdf.set_text_color(*BLACK)

# ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────────
h2(pdf,"EXECUTIVE SUMMARY")
para(pdf,
    "FaithForge operates an internal AI-powered contract screening platform that automatically scans "
    "incoming emails for RFP/RFQ/grant opportunities, reviews solicitation documents, and generates "
    "submission-ready proposal packets. The system currently runs on the Groq free tier, which imposes "
    "hard daily token limits that are consistently exceeded during normal operations.")
para(pdf,
    "This document requests authorization to subscribe to the OpenAI GPT-4o-mini API (pay-as-you-go, "
    "no minimum commitment). Total projected cost is $2.62 per month based on current usage patterns.")

highlight_box(pdf, "$2.62 / month",
    "Total projected API cost  |  $31.41 annually  |  No minimum commitment  |  Cancel anytime")

# ── CURRENT PROBLEM ───────────────────────────────────────────────────────────
h2(pdf,"CURRENT PROBLEM - GROQ FREE TIER LIMITATIONS")
two_cards(pdf,
    "FREE TIER CONSTRAINTS", [
        "100,000 token daily hard cap",
        "12,000 tokens/minute rate limit",
        "Scanning 30 emails alone consumes 85,000 tokens - leaving almost nothing for packet builds",
        "Packet builder takes 3-4 minutes due to forced retry waits on rate limit errors",
        "Daily quota exhausted by mid-day, blocking all AI operations for the rest of the day",
    ],
    "WITH GPT-4o-mini PAID", [
        "No daily token cap",
        "200,000 tokens/minute rate limit",
        "Packet builds complete in ~30 seconds (vs 3-4 minutes)",
        "All operations run without interruption throughout the day",
        "Pay only for actual usage - no wasted quota",
    ]
)

# ── AI OPERATIONS ─────────────────────────────────────────────────────────────
h2(pdf,"AI OPERATIONS BREAKDOWN")
para(pdf,"The platform uses AI for three distinct operations. Token consumption was measured directly from application code.")
table(pdf,
    ["Operation","What It Does","Calls/Run","Tokens/Run","Daily Volume"],
    [
        ["Proposal Packet Builder","Generates full submission-ready proposal (Executive Summary, Scope, Team, Budget)","6","28,511","5 builds/day"],
        ["Email Screener","Classifies emails as Relevant/Possibly/Not Relevant; extracts agency, due dates, solicitation number","1","3,328","~30 emails/day"],
        ["Document Reviewer","Reads uploaded solicitation docs; extracts eligibility, forms, checklist, evaluation criteria","1","4,570","~3 reviews/day"],
    ],
    [44,70,18,20,22]
)

# ── MONTHLY COST ──────────────────────────────────────────────────────────────
h2(pdf,"MONTHLY COST DETAIL")
para(pdf,"Pricing: GPT-4o-mini - $0.15 per 1M input tokens / $0.60 per 1M output tokens (verified from OpenAI pricing page, June 2026).")
table(pdf,
    ["Operation","Monthly Volume","Input Tokens","Output Tokens","Input Cost","Output Cost","Subtotal"],
    [
        ["Packet Builder","150 builds","1.70M","2.58M","$0.25","$1.55","$1.80"],
        ["Email Screener","900 emails","2.46M","0.54M","$0.37","$0.32","$0.69"],
        ["Document Reviewer","90 reviews","0.28M","0.14M","$0.04","$0.08","$0.12"],
    ],
    [36,26,22,24,22,24,20],
    footer_row=["TOTAL MONTHLY","-","4.44M","3.26M","$0.66","$1.95","$2.62"]
)

# ── SCENARIOS ─────────────────────────────────────────────────────────────────
h2(pdf,"USAGE SCENARIO ANALYSIS")
para(pdf,"Projected cost under different usage intensities. Even at maximum conceivable usage the cost remains under $10/month.")
table(pdf,
    ["Scenario","Emails/Day","Doc Reviews/Day","Packet Builds/Day","Monthly Cost"],
    [
        ["Current / Projected (Recommended)","30","3","5","$2.62"],
        ["Heavy Usage","100","5","5","$5.22"],
        ["Maximum / Worst Case","200","10","5","$8.11"],
    ],
    [74,26,34,34,20],
    winner_row=0
)

# ── ALTERNATIVES ──────────────────────────────────────────────────────────────
h2(pdf,"ALTERNATIVES CONSIDERED")
table(pdf,
    ["Option","Model","Monthly Cost","Quality","Notes"],
    [
        ["RECOMMENDED","GPT-4o-mini","$2.62","Very Good","Best price-to-quality ratio for proposal writing"],
        ["Option B","Groq Dev Tier (llama-3.3-70b)","$3.25","Good","No code changes; still has per-minute rate limits"],
        ["Option C","GPT-5.4-nano","$6.30","Good","Newer but nano-tier; 2.4x more due to output pricing"],
        ["Option D","Claude Haiku 4.5","$14.50","Best","Highest quality; output cost makes it expensive"],
        ["Option E","Groq Free Tier (current)","$0.00","Good","Daily quota exhausted mid-day; operations blocked"],
    ],
    [28,44,22,20,60],
    winner_row=0
)

# ── ROI ───────────────────────────────────────────────────────────────────────
roi_box(pdf)

# ── SETUP ─────────────────────────────────────────────────────────────────────
h2(pdf,"SETUP & BILLING")
para(pdf,"No subscription or minimum commitment. OpenAI's API is billed strictly on usage. Setup requires:")
for i,step in enumerate([
    "Create an OpenAI account at platform.openai.com",
    "Add a payment method and purchase a minimum $5 credit",
    "Generate an API key and provide it to the development team",
    "Configuration change takes under 10 minutes - no downtime",
    "Set a $10/month spend cap in the OpenAI dashboard as a safeguard",
],1):
    bullet(pdf, f"{i}. {step}")
pdf.ln(1)
para(pdf,
    "A monthly spend cap can be configured in the OpenAI dashboard to ensure costs never exceed a "
    "defined ceiling regardless of usage volume.")

# ── RECOMMENDATION ────────────────────────────────────────────────────────────
h2(pdf,"RECOMMENDATION")
s(pdf); pdf.set_fill_color(*LBLUE)
ry = pdf.get_y()
pdf.rect(L, ry, CW, 22, "F")
pdf.set_xy(L+4, ry+3)
pdf.set_font("Helvetica","B",10); pdf.set_text_color(*NAVY)
pdf.multi_cell(CW-8,6,"Authorize purchase of an OpenAI API key (GPT-4o-mini, pay-as-you-go)")
pdf.set_xy(L+4, ry+12)
pdf.set_font("Helvetica","",9); pdf.set_text_color(*DGRAY)
pdf.multi_cell(CW-8,5,
    "Initial credit: $10  |  Monthly spend cap: $10  |  Sufficient for ~4 months of normal operations")
pdf.set_xy(L, ry+22); pdf.ln(3); s(pdf)
pdf.set_text_color(*BLACK)
para(pdf,
    "This eliminates all current free-tier limitations, reduces packet build time from 3-4 minutes "
    "to approximately 30 seconds, and ensures uninterrupted AI-assisted contract screening "
    "throughout the business day.")

# ── FOOTER LINE ───────────────────────────────────────────────────────────────
pdf.ln(4); hr(pdf, NAVY)
pdf.set_font("Helvetica","",8); pdf.set_text_color(*GRAY); s(pdf)
pdf.cell(CW/2,5,"FaithForge Technologies & Consulting LLC  |  info@faithforgetech.com  |  410-862-2975")
pdf.cell(CW/2,5,"Prepared June 16, 2026  |  Internal - Budget Approval",align="R",ln=True)

out = "FaithForge_AI_API_Cost_Proposal.pdf"
pdf.output(out)
print(f"PDF saved: {out}")
