"""
Oracle Recruiting Cloud (ORC) fetcher — the candidate-experience REST API that
backs Oracle Fusion careers sites.

Each tenant is served from its own Fusion pod host, e.g.
  Honeywell → ibqbjb.fa.ocs.oraclecloud.com
  Oracle    → eeho.fa.us2.oraclecloud.com

Two different site identifiers are needed, and they are not interchangeable:
  `site_number` — the API's `siteNumber` finder argument (e.g. "CX_1001")
  `site_slug`   — the human-readable segment in public job URLs (e.g. "Honeywell")
Using `site_number` in a job URL yields a 302 to the slug form, so we build the
canonical URL directly.

Note: some tenants (Oracle's own) ignore `siteNumber` and return the full
requisition set regardless of the value passed.
"""

from fetchers import (
    http_get,
    is_relevant,
    is_us_country,
    labeled_errors,
    make_id,
    offset_paginate,
)

API_PATH = "/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
JOB_URL = "https://{host}/hcmUI/CandidateExperience/en/sites/{slug}/job/{job_id}"

LIMIT = 100
# Oracle's own tenant returns ~1800 keyword matches, so 10 pages truncated it.
MAX_PAGES = 25


def fetch(company: dict) -> list[dict]:
    host = company["host"]
    site_number = company["site_number"]
    site_slug = company["site_slug"]
    url = f"https://{host}{API_PATH}"
    jobs = []

    def fetch_page(offset: int) -> tuple[list, int]:
        # The `finder` argument is a single Oracle-specific string; its commas and
        # semicolon are structural, so it is assembled here rather than as params.
        finder = (
            f"findReqs;siteNumber={site_number},keyword=intern,"
            f"limit={LIMIT},offset={offset}"
        )
        params = {
            "onlyData": "true",
            "expand": "requisitionList",
            "finder": finder,
        }
        with labeled_errors("Oracle Recruiting Cloud", company["name"], f"offset {offset}"):
            resp = http_get(url, params=params)

        items = resp.json().get("items", [])
        if not items:
            return [], 0
        payload = items[0]
        return payload.get("requisitionList", []), payload.get("TotalJobsCount", 0)

    for postings in offset_paginate(fetch_page, LIMIT, MAX_PAGES, company["name"]):
        for req in postings:
            if not is_us_country(req.get("PrimaryLocationCountry") or ""):
                continue

            title = (req.get("Title") or "").strip()
            if not title or not is_relevant(title):
                continue

            job_id = req.get("Id") or ""
            job_url = (
                JOB_URL.format(host=host, slug=site_slug, job_id=job_id) if job_id else ""
            )

            jobs.append({
                "id": str(job_id) if job_id else make_id(company["name"], title, job_url),
                "company": company["name"],
                "title": title,
                "url": job_url,
                "location": req.get("PrimaryLocation") or "",
            })

    return jobs
