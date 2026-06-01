import argparse
import os
from collections import defaultdict
from datetime import date

import resend

RECIPIENT = "vkchaudhari2007@gmail.com"
SENDER = "Internship Tracker <onboarding@resend.dev>"


def send_success(new_jobs: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    company_count = len({j["company"] for j in new_jobs})

    subject = f"New Internship Postings — {today}"
    body = _build_success_body(new_jobs, today, company_count)

    _send(subject, body)


def send_failure(error_message: str) -> None:
    today = date.today().strftime("%B %d, %Y")
    subject = f"⚠️ Internship Tracker Failed — {today}"

    repo = os.getenv("GITHUB_REPOSITORY", "your-repo")
    body = (
        f"The internship tracker run failed with the following error:\n\n"
        f"{error_message}\n\n"
        f"Check GitHub Actions logs for full details:\n"
        f"https://github.com/{repo}/actions"
    )

    _send(subject, body)


def _build_success_body(jobs: list[dict], today: str, company_count: int) -> str:
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


def _send(subject: str, body: str) -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]

    params: resend.Emails.SendParams = {
        "from": SENDER,
        "to": [RECIPIENT],
        "subject": subject,
        "text": body,
    }

    response = resend.Emails.send(params)
    print(f"Email sent: {response['id']} — {subject}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure", metavar="ERROR", help="Send a failure alert with this message")
    args = parser.parse_args()

    if args.failure:
        send_failure(args.failure)
