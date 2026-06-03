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

from fetchers import http_get, is_relevant, make_id

BASE_URL = "https://careers.amd.com/api/jobs"
PAGE_SIZE = 100
MAX_PAGES = 10

HEADERS = {
    "Accept": "application/json",
    "Referer": "https://careers.amd.com/careers-home/jobs?keywords=intern",
}


def fetch(company: dict) -> list[dict]:
    jobs = []

    for page in range(1, MAX_PAGES + 1):
        params = {
            "keywords": "intern",
            "page": page,
            "limit": PAGE_SIZE,
        }

        try:
            resp = http_get(BASE_URL, params=params, headers=HEADERS)
        except Exception as e:
            raise RuntimeError(f"AMD fetch failed (page {page}): {e}")

        data = resp.json()
        postings = data.get("jobs", [])
        total = data.get("totalCount", 0)

        if not postings:
            break

        for posting in postings:
            d = posting.get("data", {})

            # Client-side US filter — API country param is non-functional
            country_code = (d.get("country_code") or "").upper()
            if country_code not in ("US", "USA"):
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

        # Stop paginating if we've seen all results
        if page * PAGE_SIZE >= total:
            break

    return jobs
