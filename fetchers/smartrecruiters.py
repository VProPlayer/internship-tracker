from fetchers import http_get, is_relevant, is_us_location, make_id, offset_paginate

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
JOB_URL = "https://jobs.smartrecruiters.com/{company_id}/{posting_id}"

MAX_PAGES = 10
LIMIT = 100  # SmartRecruiters caps postings page size at 100


def fetch(company: dict) -> list[dict]:
    company_id = company["company_id"]
    url = BASE_URL.format(company_id=company_id)
    jobs = []

    def fetch_page(offset: int) -> tuple[list, int]:
        try:
            resp = http_get(url, params={"limit": LIMIT, "offset": offset})
        except Exception as e:
            raise RuntimeError(f"SmartRecruiters fetch failed for {company['name']}: {e}")
        data = resp.json()
        return data.get("content", []), data.get("totalFound", 0)

    for postings in offset_paginate(fetch_page, LIMIT, MAX_PAGES, company["name"]):
        for posting in postings:
            title = posting.get("name", "")
            if not is_relevant(title):
                continue

            loc = posting.get("location") or {}
            location = loc.get("fullLocation") or ", ".join(
                p for p in (loc.get("city"), loc.get("region")) if p
            )

            country = loc.get("country", "")
            if country:
                is_us = country.lower() in ("us", "usa")
            else:
                is_us = is_us_location(location)

            if not is_us:
                continue

            posting_id = posting.get("id", "")
            jobs.append({
                "id": posting_id or make_id(company["name"], title, location),
                "company": company["name"],
                "title": title,
                "url": JOB_URL.format(company_id=company_id, posting_id=posting_id),
                "location": location,
            })

    return jobs
