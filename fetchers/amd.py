"""
AMD fetcher — uses the undocumented Jibe job-search API served by careers.amd.com.

The public iCIMS portal (internal-amd.icims.com) blocks headless access and the
public-facing endpoint (careers-amd.icims.com) returns only a JS redirect.
However, the Jibe SPA loaded at careers.amd.com makes XHR requests to
  GET /api/jobs?keywords=intern&page=N&limit=100
which returns a clean JSON payload with full job metadata including country_code.
We filter client-side for country_code == "US" since the API's own country param
returns 0 results regardless of value.
"""

from fetchers import (
    http_get,
    is_relevant,
    is_us_country,
    labeled_errors,
    make_id,
    offset_paginate,
)

BASE_URL = "https://careers.amd.com/api/jobs"
PAGE_SIZE = 100
MAX_PAGES = 10

HEADERS = {
    "Accept": "application/json",
    "Referer": "https://careers.amd.com/careers-home/jobs?keywords=intern",
}


def fetch(company: dict) -> list[dict]:
    jobs = []

    def fetch_page(offset: int) -> tuple[list, int]:
        # This API paginates by 1-based page number, not offset.
        page = offset // PAGE_SIZE + 1
        params = {
            "keywords": "intern",
            "page": page,
            "limit": PAGE_SIZE,
        }
        with labeled_errors("AMD", company["name"], f"page {page}"):
            resp = http_get(BASE_URL, params=params, headers=HEADERS)
        data = resp.json()
        return data.get("jobs", []), data.get("totalCount", 0)

    for postings in offset_paginate(fetch_page, PAGE_SIZE, MAX_PAGES, company["name"]):
        for posting in postings:
            d = posting.get("data", {})

            # Client-side US filter — API country param is non-functional
            if not is_us_country(d.get("country_code") or ""):
                continue

            title = d.get("title", "").strip()
            if not title or not is_relevant(title):
                continue

            slug = d.get("slug") or d.get("req_id", "")
            url = f"https://careers.amd.com/jobs/{slug}?lang=en-us" if slug else ""
            if not url:
                continue

            city = d.get("city", "")
            state = d.get("state", "")
            location = f"{city}, {state}".strip(", ") if (city or state) else d.get("full_location", "")

            jobs.append({
                "id": str(slug) if slug else make_id(company["name"], title, url),
                "company": company["name"],
                "title": title,
                "url": url,
                "location": location,
            })

    return jobs
