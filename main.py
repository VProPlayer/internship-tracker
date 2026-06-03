import json
import os
import sys
import traceback

from dotenv import load_dotenv

from fetchers import greenhouse, workday, icims, jina, ashby, amazon, phenom
import diff
import notify

load_dotenv()

FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "workday": workday.fetch,
    "icims": icims.fetch,
    "ashby": ashby.fetch,
    "amazon": amazon.fetch,
    "phenom": phenom.fetch,
    "custom": jina.fetch,
}

_HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES_FILE = os.path.join(_HERE, "companies.json")


def main():
    with open(COMPANIES_FILE) as f:
        companies = json.load(f)

    all_fetched = []
    errors = []

    for company in companies:
        fetcher_type = company.get("type")
        fetcher = FETCHERS.get(fetcher_type)

        if not fetcher:
            msg = f"{company['name']}: unknown type '{fetcher_type}'"
            print(f"[SKIP] {msg}")
            errors.append(msg)
            continue

        try:
            jobs = fetcher(company)
            print(f"[OK] {company['name']}: {len(jobs)} relevant posting(s)")
            all_fetched.extend(jobs)
        except Exception as e:
            msg = f"{company['name']}: {e}"
            print(f"[ERROR] {msg}")
            errors.append(msg)

    new_jobs = diff.find_new_jobs(all_fetched)
    print(f"\n{len(new_jobs)} new job(s) found.")

    if new_jobs:
        notify.send_success(new_jobs)
        diff.mark_notified([j["id"] for j in new_jobs])

    if errors:
        print(f"\n{len(errors)} company/companies had errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_msg = traceback.format_exc()
        print(f"Fatal error:\n{error_msg}")
        try:
            notify.send_failure(error_msg)
        except Exception as notify_err:
            print(f"Also failed to send failure email: {notify_err}")
        sys.exit(1)
