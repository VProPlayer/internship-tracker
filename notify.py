import argparse
import os
from collections import defaultdict
from datetime import date
from html import escape

import resend

RECIPIENT = os.environ["RECIPIENT_EMAIL"]
SENDER = "Internship Tracker <onboarding@resend.dev>"

# Set once at import time — load_dotenv() is called before this module is imported
resend.api_key = os.getenv("RESEND_API_KEY", "")

# ── Material Expressive Dark — design tokens ──────────────────────────────────
# Surface hierarchy: bg (#0F1117) → surface (#1A1D27) → surface-variant (#22263A)
# Primary tonal:    #A8C7FA (Google Blue tonal, dark-mode safe, AA-contrast)
# On-surface:       #E2E2EC (high-emphasis text)
# On-surface-var:   #C4C6D0 (medium-emphasis text)
# Outline:          #44475A (subtle borders)

_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Google+Sans+Display:wght@700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: #0F1117;
    font-family: 'Google Sans', 'Roboto', Arial, sans-serif;
    color: #E2E2EC;
    -webkit-font-smoothing: antialiased;
  }

  .wrapper {
    background-color: #0F1117;
    padding: 32px 16px 48px;
  }

  .container {
    max-width: 600px;
    margin: 0 auto;
  }

  /* ── Header ── */
  .header {
    text-align: left;
    padding: 0 0 28px 0;
    border-bottom: 1px solid #44475A;
    margin-bottom: 28px;
  }

  .header-eyebrow {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: #A8C7FA;
    margin-bottom: 8px;
  }

  .header-title {
    font-family: 'Google Sans Display', 'Google Sans', Arial, sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #E2E2EC;
    line-height: 1.2;
  }

  .header-subtitle {
    margin-top: 8px;
    font-size: 13px;
    color: #C4C6D0;
    line-height: 1.5;
  }

  /* ── Summary pill ── */
  .summary-pill {
    display: inline-block;
    background-color: #1E3A5F;
    border: 1px solid #2D5F9E;
    border-radius: 100px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 500;
    color: #A8C7FA;
    margin-bottom: 28px;
  }

  /* ── Company section ── */
  .company-section {
    margin-bottom: 20px;
  }

  .company-header {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }

  .company-name {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #A8C7FA;
  }

  .company-count {
    margin-left: 10px;
    background-color: #1E3A5F;
    border-radius: 100px;
    padding: 2px 9px;
    font-size: 10px;
    font-weight: 500;
    color: #A8C7FA;
  }

  /* ── Job card ── */
  .job-card {
    background-color: #1A1D27;
    border: 1px solid #2C2F3F;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 8px;
  }

  .job-card:last-child {
    margin-bottom: 0;
  }

  .job-title {
    font-size: 15px;
    font-weight: 600;
    color: #E2E2EC;
    line-height: 1.4;
    margin-bottom: 6px;
  }

  .job-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .job-location {
    font-size: 12px;
    color: #C4C6D0;
  }

  .job-location::before {
    content: '📍 ';
  }

  .apply-btn {
    display: inline-block;
    background-color: #A8C7FA;
    color: #001D36 !important;
    text-decoration: none;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.3px;
    border-radius: 100px;
    padding: 7px 18px;
    line-height: 1;
  }

  /* ── Footer ── */
  .footer {
    border-top: 1px solid #44475A;
    margin-top: 36px;
    padding-top: 20px;
    text-align: center;
    font-size: 11px;
    color: #6B6F80;
    line-height: 1.7;
  }

  .footer a {
    color: #7CA8E0;
    text-decoration: none;
  }

  /* ── Failure card ── */
  .failure-card {
    background-color: #2A1A1A;
    border: 1px solid #5C2E2E;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
  }

  .failure-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #FFB4AB;
    margin-bottom: 8px;
  }

  .failure-title {
    font-size: 18px;
    font-weight: 700;
    color: #FFB4AB;
    margin-bottom: 12px;
  }

  .failure-body {
    font-size: 13px;
    color: #C4C6D0;
    line-height: 1.7;
  }

  .failure-pre {
    background-color: #1A0E0E;
    border: 1px solid #5C2E2E;
    border-radius: 10px;
    padding: 14px;
    margin-top: 14px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #FFCDD2;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.6;
  }

  .actions-btn {
    display: inline-block;
    margin-top: 18px;
    background-color: #FFB4AB;
    color: #690005 !important;
    text-decoration: none;
    font-size: 12px;
    font-weight: 700;
    border-radius: 100px;
    padding: 8px 20px;
  }
"""


def send_success(new_jobs: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    company_count = len({j["company"] for j in new_jobs})

    subject = f"New Internship Postings — {today}"
    text_body = _build_success_text(new_jobs, today, company_count)
    html_body = _build_success_html(new_jobs, today, company_count)

    _send(subject, text_body, html_body)


def send_failure(error_message: str) -> None:
    today = date.today().strftime("%B %d, %Y")
    subject = f"⚠️ Internship Tracker Failed — {today}"

    repo = os.getenv("GITHUB_REPOSITORY", "your-repo")
    actions_url = f"https://github.com/{repo}/actions"

    text_body = (
        f"The internship tracker run failed with the following error:\n\n"
        f"{error_message}\n\n"
        f"Check GitHub Actions logs for full details:\n"
        f"{actions_url}"
    )
    html_body = _build_failure_html(error_message, today, actions_url)

    _send(subject, text_body, html_body)


# ── Plain-text builders ───────────────────────────────────────────────────────

def _build_success_text(jobs: list[dict], today: str, company_count: int) -> str:
    grouped = defaultdict(list)
    for job in jobs:
        grouped[job["company"]].append(job)

    lines = [
        f"{len(jobs)} new posting(s) found across {company_count} company/companies.",
        "",
    ]

    for company in sorted(grouped.keys()):
        lines.append(company)
        for job in grouped[company]:
            location = f" | {job['location']}" if job.get("location") else ""
            lines.append(f"  - {job['title']}{location} | Apply: {job['url']}")
        lines.append("")

    return "\n".join(lines).strip()


# ── HTML builders ─────────────────────────────────────────────────────────────

def _html_shell(content: str) -> str:
    """Wrap content in the full HTML document with Material Expressive dark styles."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark">
  <title>Internship Tracker</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      {content}
      <div class="footer">
        Sent by <strong>Internship Tracker</strong> &mdash; automated weekday digest<br>
        Powered by Resend &bull; Deduplicated via Supabase
      </div>
    </div>
  </div>
</body>
</html>"""


def _build_success_html(jobs: list[dict], today: str, company_count: int) -> str:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for job in jobs:
        grouped[job["company"]].append(job)

    sections = []
    for company in sorted(grouped.keys()):
        company_jobs = grouped[company]
        count_badge = f'<span class="company-count">{len(company_jobs)}</span>' if len(company_jobs) > 1 else ""

        cards = []
        for job in company_jobs:
            title = escape(job["title"])
            url = escape(job["url"])
            location_html = ""
            if job.get("location"):
                location_html = f'<span class="job-location">{escape(job["location"])}</span>'

            cards.append(f"""
      <div class="job-card">
        <div class="job-title">{title}</div>
        <div class="job-meta">
          {location_html}
        </div>
        <a class="apply-btn" href="{url}" target="_blank" rel="noopener noreferrer">Apply Now</a>
      </div>""")

        sections.append(f"""
    <div class="company-section">
      <div class="company-header">
        <span class="company-name">{escape(company)}</span>
        {count_badge}
      </div>
      {"".join(cards)}
    </div>""")

    posting_word = "posting" if len(jobs) == 1 else "postings"
    company_word = "company" if company_count == 1 else "companies"

    content = f"""
      <div class="header">
        <div class="header-eyebrow">Internship Digest</div>
        <div class="header-title">New Postings Found</div>
        <div class="header-subtitle">{today}</div>
      </div>

      <div class="summary-pill">
        {len(jobs)} new {posting_word} across {company_count} {company_word}
      </div>

      {"".join(sections)}
    """

    return _html_shell(content)


def _build_failure_html(error_message: str, today: str, actions_url: str) -> str:
    escaped_error = escape(error_message)

    content = f"""
      <div class="header">
        <div class="header-eyebrow">System Alert</div>
        <div class="header-title">Tracker Run Failed</div>
        <div class="header-subtitle">{today}</div>
      </div>

      <div class="failure-card">
        <div class="failure-label">Error</div>
        <div class="failure-title">The tracker encountered a fatal error</div>
        <div class="failure-body">
          The scheduled run did not complete successfully.
          Review the GitHub Actions logs for the full stack trace.
          <div class="failure-pre">{escaped_error}</div>
        </div>
        <a class="actions-btn" href="{escape(actions_url)}" target="_blank" rel="noopener noreferrer">
          View Actions Logs
        </a>
      </div>
    """

    return _html_shell(content)


# ── Resend dispatch ───────────────────────────────────────────────────────────

def _send(subject: str, text_body: str, html_body: str) -> None:
    params: resend.Emails.SendParams = {
        "from": SENDER,
        "to": [RECIPIENT],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }

    response = resend.Emails.send(params)
    print(f"Email sent: {response['id']} — {subject}")


# ── CLI test harness ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    resend.api_key = os.environ["RESEND_API_KEY"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--failure", metavar="ERROR", help="Send a failure alert with this message")
    parser.add_argument("--test", action="store_true", help="Send a test success email with mock data")
    args = parser.parse_args()

    if args.failure:
        send_failure(args.failure)
    elif args.test:
        mock_jobs = [
            {"company": "ACME CORP", "title": "Software Engineering Intern", "url": "https://example.com/jobs/1", "location": "San Francisco, CA"},
            {"company": "ACME CORP", "title": "Machine Learning Intern", "url": "https://example.com/jobs/2", "location": "Remote"},
            {"company": "INITECH", "title": "Data Engineering Co-op", "url": "https://example.com/jobs/3", "location": "Austin, TX"},
        ]
        send_success(mock_jobs)
    else:
        parser.print_help()
