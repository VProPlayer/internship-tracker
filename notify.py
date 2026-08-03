import argparse
import os
import smtplib
import ssl
import time
from collections import defaultdict
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from dotenv import load_dotenv

from fetchers import jina

# Idempotent — main.py also calls this. Needed here so `python notify.py --test`
# works standalone, since the constants below read the environment at import.
load_dotenv()

# The digest is addressed to a Google Group, which fans it out to every member
# and handles subscriptions, unsubscribes and archiving. One message per run.
RECIPIENT = os.environ["RECIPIENT_EMAIL"]

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Matches the 3-attempt retry the fetchers get via http_get — a transient SMTP
# hiccup would otherwise discard the whole digest until tomorrow's run.
SMTP_MAX_ATTEMPTS = 3

SENDER = formataddr(("Internship Tracker", SMTP_USER))

# Failure alerts are operational noise for subscribers — they go to the
# maintainer alone, never to the group.
OWNER_EMAIL = os.getenv("OWNER_EMAIL") or SMTP_USER

# Google Form for requesting a company be added to the tracker.
REQUEST_FORM_URL = "https://forms.gle/coZd4rP7JtiTjFFW6"

# ── Material 3 Expressive — light/dark design tokens ──────────────────────────
# The template ships light by default and overrides to dark under
# `prefers-color-scheme: dark`, which Apple Mail and modern Gmail honour. Colours
# follow the Material 3 baseline blue scheme so both modes stay AA-contrast.
#
#                     LIGHT                    DARK
#   page bg          #F4F5FB                  #111318
#   surface (card)   #FFFFFF                  #1D2024
#   primary          #415F91  on #FFFFFF      #A8C7FA  on #0A305F
#   primary-container#D9E2FF  on #0E1B37      #284777  on #D9E2FF
#   on-surface       #191C20                  #E2E2E9
#   on-surface-var   #44474E                  #C4C6CF
#   outline-variant  #C4C6D0                  #33363C

def send_success(new_jobs: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    company_count = len({j["company"] for j in new_jobs})

    subject = f"New Internship Postings — {today}"
    text_body = _build_success_text(new_jobs, today, company_count)
    html_body = _build_success_html(new_jobs, today, company_count)

    _send(subject, text_body, html_body, RECIPIENT)


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

    _send(subject, text_body, html_body, OWNER_EMAIL)


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

    lines.append(f"Want a company added? Request one: {REQUEST_FORM_URL}")

    return "\n".join(lines).strip()


# ── HTML builders ─────────────────────────────────────────────────────────────

def _jina_usage_html() -> str:
    """Render a footer line with remaining Jina token balances, or '' if unavailable."""
    summary = jina.usage_summary()
    if not summary:
        return ""
    parts = [f"{e['label']}: {e['remaining']:,} tokens" for e in summary]
    return "<br>Jina balance &mdash; " + " &bull; ".join(parts)


def _request_company_html() -> str:
    """Render the footer link to the request-a-company form."""
    return (
        f'<br><a href="{escape(REQUEST_FORM_URL)}" '
        f'target="_blank" rel="noopener noreferrer">Request a company</a>'
    )


def _html_shell(content: str) -> str:
    """Wrap content in the full HTML document with Material Expressive dark styles."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Internship Tracker</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      {content}
      <div class="footer">
        Sent by <strong>Internship Tracker</strong> &mdash; automated weekday digest<br>
        Deduplicated from an in-repo ledger{_jina_usage_html()}{_request_company_html()}
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


# ── SMTP dispatch ─────────────────────────────────────────────────────────────

def _send(subject: str, text_body: str, html_body: str, to: str) -> None:
    if not to:
        raise RuntimeError("No recipient configured — set RECIPIENT_EMAIL (and OWNER_EMAIL)")
    if not (SMTP_USER and SMTP_PASSWORD):
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD must be set to send mail")

    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    last_exc: Exception | None = None

    for attempt in range(SMTP_MAX_ATTEMPTS):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            print(f"Email sent to {to} — {subject}")
            return
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
            # Bad credentials, or the group rejected the post. Neither self-heals,
            # and retrying a rejected login risks tripping Google's lockout.
            raise
        except (smtplib.SMTPException, OSError) as e:
            last_exc = e
            if attempt < SMTP_MAX_ATTEMPTS - 1:
                wait = 5 * (2 ** attempt)  # 5s, 10s
                print(f"SMTP send failed ({e}) — retrying in {wait}s")
                time.sleep(wait)

    raise RuntimeError(f"Email to {to} failed after {SMTP_MAX_ATTEMPTS} attempts: {last_exc}")


# ── CLI test harness ──────────────────────────────────────────────────────────

if __name__ == "__main__":
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



# ── Email stylesheet ─────────────────────────────────────────────────────────
# Kept at the bottom: it is markup, not logic, and sat between the config and
# the send/build functions that actually need reading.

_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Google+Sans+Display:wght@600;700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background-color: #F4F5FB;
    font-family: 'Google Sans', 'Roboto', Arial, sans-serif;
    color: #191C20;
    -webkit-font-smoothing: antialiased;
  }

  .wrapper {
    background-color: #F4F5FB;
    padding: 32px 16px 48px;
  }

  .container {
    max-width: 600px;
    margin: 0 auto;
  }

  /* ── Header (expressive tonal hero) ── */
  .header {
    background-color: #D9E2FF;
    border-radius: 28px;
    padding: 28px 28px 30px;
    margin-bottom: 24px;
  }

  .header-eyebrow {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: #2E4B7A;
    margin-bottom: 10px;
  }

  .header-title {
    font-family: 'Google Sans Display', 'Google Sans', Arial, sans-serif;
    font-size: 30px;
    font-weight: 700;
    color: #0E1B37;
    line-height: 1.15;
    letter-spacing: -0.4px;
  }

  .header-subtitle {
    margin-top: 8px;
    font-size: 13px;
    color: #3A4B68;
    line-height: 1.5;
  }

  /* ── Summary pill ── */
  .summary-pill {
    display: inline-block;
    background-color: #415F91;
    border-radius: 100px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
    color: #FFFFFF;
    margin-bottom: 26px;
  }

  /* ── Company section ── */
  .company-section {
    margin-bottom: 22px;
  }

  .company-header {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    padding-left: 4px;
  }

  .company-name {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    color: #415F91;
  }

  .company-count {
    margin-left: 10px;
    background-color: #D9E2FF;
    border-radius: 100px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 600;
    color: #0E1B37;
  }

  /* ── Job card ── */
  .job-card {
    background-color: #FFFFFF;
    border: 1px solid #E1E2EC;
    border-radius: 24px;
    padding: 18px 20px;
    margin-bottom: 10px;
  }

  .job-card:last-child {
    margin-bottom: 0;
  }

  .job-title {
    font-size: 16px;
    font-weight: 600;
    color: #191C20;
    line-height: 1.4;
    margin-bottom: 8px;
  }

  .job-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }

  .job-location {
    font-size: 12px;
    color: #44474E;
  }

  .job-location::before {
    content: '📍 ';
  }

  .apply-btn {
    display: inline-block;
    background-color: #415F91;
    color: #FFFFFF !important;
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    border-radius: 100px;
    padding: 9px 20px;
    line-height: 1;
  }

  /* ── Footer ── */
  .footer {
    border-top: 1px solid #C4C6D0;
    margin-top: 36px;
    padding-top: 20px;
    text-align: center;
    font-size: 11px;
    color: #74777F;
    line-height: 1.7;
  }

  .footer a {
    color: #415F91;
    text-decoration: none;
  }

  /* ── Failure card ── */
  .failure-card {
    background-color: #FFDAD6;
    border-radius: 24px;
    padding: 24px;
    margin-bottom: 24px;
  }

  .failure-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #8C1D18;
    margin-bottom: 8px;
  }

  .failure-title {
    font-size: 18px;
    font-weight: 700;
    color: #410002;
    margin-bottom: 12px;
  }

  .failure-body {
    font-size: 13px;
    color: #5C3A38;
    line-height: 1.7;
  }

  .failure-pre {
    background-color: #FFF0EE;
    border: 1px solid #F3B7B1;
    border-radius: 12px;
    padding: 14px;
    margin-top: 14px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #7A1912;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.6;
  }

  .actions-btn {
    display: inline-block;
    margin-top: 18px;
    background-color: #BA1A1A;
    color: #FFFFFF !important;
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    border-radius: 100px;
    padding: 10px 22px;
  }

  /* ── Dark mode ── */
  @media (prefers-color-scheme: dark) {
    body, .wrapper { background-color: #111318 !important; }
    body { color: #E2E2E9 !important; }

    .header { background-color: #284777 !important; }
    .header-eyebrow { color: #AEC6FF !important; }
    .header-title { color: #F5F8FF !important; }
    .header-subtitle { color: #C6D3EC !important; }

    .summary-pill { background-color: #A8C7FA !important; color: #0A305F !important; }

    .company-name { color: #A8C7FA !important; }
    .company-count { background-color: #284777 !important; color: #D9E2FF !important; }

    .job-card { background-color: #1D2024 !important; border-color: #33363C !important; }
    .job-title { color: #E2E2E9 !important; }
    .job-location { color: #C4C6CF !important; }
    .apply-btn { background-color: #A8C7FA !important; color: #0A305F !important; }

    .footer { border-top-color: #33363C !important; color: #8E9099 !important; }
    .footer a { color: #A8C7FA !important; }

    .failure-card { background-color: #2A1A1A !important; }
    .failure-label { color: #FFB4AB !important; }
    .failure-title { color: #FFDAD6 !important; }
    .failure-body { color: #E7BDB8 !important; }
    .failure-pre { background-color: #1A0E0E !important; border-color: #5C2E2E !important; color: #FFCDD2 !important; }
    .actions-btn { background-color: #FFB4AB !important; color: #690005 !important; }
  }
"""