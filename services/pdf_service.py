"""
pdf_service.py
==============
Generates A4-format PDF reports using fpdf2.

Public API:
    generate_task_report_pdf(report_data)   → Flask Response
    generate_user_report_pdf(report_data)   → Flask Response
"""

from flask import make_response
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(text) -> str:
    """Encode value to latin-1-safe string for fpdf."""
    if text is None:
        return "N/A"
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _fmt_date(val) -> str:
    """Format a date/datetime value to a readable string."""
    if not val:
        return "N/A"
    s = str(val)
    # Trim microseconds if present
    return s[:19] if len(s) >= 19 else s


# ---------------------------------------------------------------------------
# PDF Builder  (Professional Word-Style Format)
# ---------------------------------------------------------------------------

class _ReportPDF(FPDF):
    """Clean, professional A4 report — white background, dark-navy header."""

    # Colour palette
    NAVY        = (23, 37, 84)     # deep navy  — header bar
    ACCENT      = (30, 100, 200)   # blue        — section ruling line
    TEXT_DARK   = (20, 20, 20)     # near-black  — body text
    TEXT_MUTED  = (100, 100, 110)  # mid-grey    — labels / footer
    SECTION_BG  = (240, 243, 248)  # very light blue-grey — section header fill
    WHITE       = (255, 255, 255)
    SUCCESS     = (33, 128, 79)
    WARNING_COL = (161, 110, 10)
    DANGER      = (185, 28, 28)
    TABLE_HDR   = (220, 230, 245)  # light blue  — table header row
    TABLE_ALT   = (248, 249, 252)  # table alt row

    def __init__(self, report_id: str, generated_on: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.report_id    = report_id
        self.generated_on = generated_on
        self.set_margins(left=20, top=10, right=20)

    # ----  Page header  -------------------------------------------------------

    def header(self):
        # Navy header bar
        self.set_fill_color(*self.NAVY)
        self.rect(0, 0, 210, 22, "F")

        # Organisation name  (left, white)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 11)
        self.set_xy(20, 5)
        self.cell(80, 7, "EXCUSE PATTERN AI", ln=0)

        # Report title  (right, white)
        self.set_font("Helvetica", "", 9)
        self.set_xy(100, 5)
        self.cell(90, 7, "AI Delay Analysis Report", ln=0, align="R")

        # Thin sub-line: report ID + date
        self.set_font("Helvetica", "", 7)
        self.set_text_color(190, 200, 220)
        self.set_xy(20, 13)
        self.cell(170, 5,
                  f"Report ID: {_safe(self.report_id)}     |     Generated: {_safe(self.generated_on)}",
                  ln=False, align="L")

        self.set_text_color(*self.TEXT_DARK)
        self.ln(18)

    # ----  Page footer  -------------------------------------------------------

    def footer(self):
        self.set_y(-14)
        # Thin ruling line
        self.set_draw_color(*self.TEXT_MUTED)
        self.set_line_width(0.3)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*self.TEXT_MUTED)
        self.cell(0, 5,
                  "Confidential — Issued by Excuse Pattern AI Intelligence Engine",
                  align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R")

    # ----  Section helpers  ---------------------------------------------------

    def section_header(self, title: str):
        """Prints a bold section heading with a blue left accent bar."""
        self.ln(5)
        # Blue left bar
        self.set_fill_color(*self.ACCENT)
        self.rect(self.get_x(), self.get_y(), 3, 7, "F")
        # Light fill behind the title
        self.set_fill_color(*self.SECTION_BG)
        self.set_text_color(*self.NAVY)
        self.set_font("Helvetica", "B", 9)
        # indent past the bar
        x = self.get_x()
        self.set_x(x + 4)
        self.cell(0, 7, title.upper(), ln=True, fill=True)
        self.set_text_color(*self.TEXT_DARK)
        self.ln(1)

    def kv_row(self, label: str, value: str, label_w: float = 58):
        """Key-value pair row — bold label left, value right."""
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*self.TEXT_MUTED)
        self.cell(label_w, 6, _safe(label), ln=0)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.TEXT_DARK)
        self.multi_cell(0, 6, _safe(value))

    def verdict_badge(self, verdict: str):
        """Inline coloured badge for the AI verdict."""
        color_map = {
            "REAL":       self.SUCCESS,
            "SUSPICIOUS": self.WARNING_COL,
            "FAKE":       self.DANGER,
        }
        color = color_map.get(verdict.upper(), self.TEXT_MUTED)
        self.set_fill_color(*color)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 8.5)
        self.cell(30, 7, f"  {_safe(verdict)}  ", fill=True, ln=True)
        self.set_text_color(*self.TEXT_DARK)



# ---------------------------------------------------------------------------
# Single-Task Report PDF
# ---------------------------------------------------------------------------

def generate_task_report_pdf(report_data: dict):
    """
    Builds an A4 PDF for a single-task delay analysis report.
    Returns a Flask Response suitable for direct return from a route.
    """
    pdf = _ReportPDF(
        report_id    = report_data.get("report_id", ""),
        generated_on = report_data.get("generated_on", ""),
    )
    pdf.add_page()

    user  = report_data.get("user",  {})
    task  = report_data.get("task",  {})
    delay = report_data.get("delay", {})
    doc   = report_data.get("document")
    scores = report_data.get("scores", {})
    has_delay = report_data.get("has_delay", False)

    # ---- Section 1: Employee Information ----
    pdf.section_header("SECTION 1 — EMPLOYEE INFORMATION")
    pdf.kv_row("Full Name:",    user.get("name", "N/A"))
    pdf.kv_row("Email:",        user.get("email", "N/A"))
    pdf.kv_row("System Role:",  user.get("role", "N/A"))
    pdf.kv_row("Job Role:",     user.get("job_role", "Not specified"))

    # ---- Section 2: Task Information ----
    pdf.section_header("SECTION 2 — TASK INFORMATION")
    pdf.kv_row("Task Title:",       task.get("title",       "N/A"))
    pdf.kv_row("Priority:",         task.get("priority",    "N/A"))
    pdf.kv_row("Complexity Weight:",str(task.get("complexity", 1)))
    pdf.kv_row("Deadline:",         _fmt_date(task.get("deadline")))
    pdf.kv_row("Submitted At:",     _fmt_date(task.get("created_at")))
    pdf.kv_row("Status:",           task.get("status",      "N/A"))
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
    pdf.cell(55, 6, "Description:", ln=0)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_ReportPDF.TEXT_DARK)
    pdf.multi_cell(0, 6, _safe(task.get("description", "N/A")))

    # ---- Section 3: Delay Details ----
    pdf.section_header("SECTION 3 — DELAY DETAILS")
    if not has_delay:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(34, 197, 94)
        pdf.cell(0, 7, "  Task completed on time. No delay recorded.", ln=True)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)
    else:
        pdf.kv_row("Delay Duration:", f"{delay.get('delay_days', 0)} day(s)")
        pdf.kv_row("Delay Category:", delay.get("category", "N/A"))
        pdf.kv_row("AI Confidence:", f"{delay.get('confidence', 0)}%")
        pdf.kv_row("Sentiment:",     f"{delay.get('sentiment_polarity', 0)} ({delay.get('sentiment_label', 'N/A')})")
        pdf.kv_row("Submitted:",     _fmt_date(delay.get("submitted_at")))

        # Verdict badge
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
        pdf.cell(55, 7, "AI Verdict:", ln=0)
        pdf.verdict_badge(delay.get("verdict", "UNKNOWN"))

        pdf.kv_row("Fake Score:",    f"{delay.get('fake_score', 0)}/100")
        pdf.kv_row("Verdict Basis:", delay.get("verdict_reason", "N/A"))

        # Reason text (potentially long)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
        pdf.cell(55, 6, "Delay Reason:", ln=0)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)
        pdf.multi_cell(0, 6, _safe(delay.get("reason_text", "N/A")))

    # ---- Section 4: Supporting Document ----
    pdf.section_header("SECTION 4 — SUPPORTING DOCUMENT")
    if doc:
        pdf.kv_row("Document Name:", doc.get("name", "N/A"))
        pdf.kv_row("File Type:",     doc.get("file_type", "N/A"))
        pdf.kv_row("Uploaded At:",   _fmt_date(doc.get("uploaded_at")))
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
        pdf.cell(0, 7, "  No supporting document submitted.", ln=True)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)

    # ---- Section 5: AI Evaluation Summary ----
    pdf.section_header("SECTION 5 — AI EVALUATION SUMMARY")
    if scores:
        pdf.kv_row("Authenticity Score:", f"{scores.get('authenticity', 0)}/100")
        pdf.kv_row("Avoidance Score:",    f"{scores.get('avoidance', 0)}/100")
        pdf.kv_row("Risk Level:",         scores.get("risk_level", "N/A"))
        pdf.kv_row("Pattern Frequency:",  str(scores.get("pattern_frequency", 0)) + " delay(s) on record")
        pdf.kv_row("Reliability Index:",  str(scores.get("reliability_index", "N/A")))
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
        pdf.cell(0, 7, "  Analysis not available.", ln=True)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)

    # ---- Section 6: AI Conclusion ----
    pdf.section_header("SECTION 6 — OVERALL AI CONCLUSION")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*_ReportPDF.TEXT_DARK)
    pdf.multi_cell(0, 6, _safe(report_data.get("conclusion", "No conclusion available.")))

    # ---- Build Response ----
    report_id = report_data.get("report_id", "report")
    response = make_response(pdf.output())
    response.headers["Content-Disposition"] = f'attachment; filename="{report_id}.pdf"'
    response.headers["Content-Type"] = "application/pdf"
    return response


# ---------------------------------------------------------------------------
# Consolidated User Report PDF
# ---------------------------------------------------------------------------

def generate_user_report_pdf(report_data: dict):
    """
    Builds an A4 PDF for a consolidated user delay report.
    Returns a Flask Response.
    """
    pdf = _ReportPDF(
        report_id    = report_data.get("report_id", ""),
        generated_on = report_data.get("generated_on", ""),
    )
    pdf.add_page()

    user  = report_data.get("user", {})
    stats = report_data.get("stats", {})
    delay_rows = report_data.get("delay_rows", [])

    # ---- Section 1: Employee Information ----
    pdf.section_header("SECTION 1 — EMPLOYEE INFORMATION")
    pdf.kv_row("Full Name:",   user.get("name",     "N/A"))
    pdf.kv_row("Email:",       user.get("email",    "N/A"))
    pdf.kv_row("System Role:", user.get("role",     "N/A"))
    pdf.kv_row("Job Role:",    user.get("job_role", "Not specified"))

    # ---- Section 2: Delay Summary Statistics ----
    pdf.section_header("SECTION 2 — DELAY SUMMARY STATISTICS")
    pdf.kv_row("Total Tasks:",          str(stats.get("total_tasks", 0)))
    pdf.kv_row("Total Delays:",         str(stats.get("total_delays", 0)))
    pdf.kv_row("Delay Rate:",           f"{stats.get('delay_rate', 0)}%")
    pdf.kv_row("Most Common Category:", stats.get("most_common_category", "N/A"))
    pdf.kv_row("Avg Sentiment:",        str(stats.get("avg_sentiment", 0)))
    pdf.kv_row("Avg Risk Score:",       f"{stats.get('avg_risk_score', 0)}%")

    # ---- Section 3: Delay Record Table ----
    pdf.section_header("SECTION 3 — DELAY RECORDS")
    if not delay_rows:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*_ReportPDF.TEXT_MUTED)
        pdf.cell(0, 7, "  No delay records found.", ln=True)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)
    else:
        # Table header row
        pdf.set_fill_color(*_ReportPDF.TABLE_HDR)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_ReportPDF.NAVY)
        col_w = [70, 22, 36, 24, 22]
        headers = ["Task", "Days Late", "Category", "Confidence", "Risk"]
        for h, w in zip(headers, col_w):
            pdf.cell(w, 7, h, border=1, fill=True)
        pdf.ln()

        # Table rows (alternating fill)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*_ReportPDF.TEXT_DARK)
        for i, row in enumerate(delay_rows):
            task_title = _safe(row.get("task_title", ""))[:38]
            cells = [
                task_title,
                str(row.get("delay_days", 0)) + "d",
                _safe(row.get("category", ""))[:18],
                f"{row.get('confidence', 0)}%",
                _safe(row.get("risk_level", "")),
            ]
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(*_ReportPDF.TABLE_ALT)
            for val, w in zip(cells, col_w):
                pdf.cell(w, 6, val, border=1, fill=fill)
            pdf.ln()

    # ---- Section 4: AI Conclusion ----
    pdf.section_header("SECTION 4 — OVERALL AI CONCLUSION")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*_ReportPDF.TEXT_DARK)
    pdf.multi_cell(0, 6, _safe(report_data.get("conclusion", "No conclusion available.")))

    # ---- Build Response ----
    report_id = report_data.get("report_id", "user_report")
    response = make_response(pdf.output())
    response.headers["Content-Disposition"] = f'attachment; filename="{report_id}.pdf"'
    response.headers["Content-Type"] = "application/pdf"
    return response
