from fetchers import http_post, is_relevant, is_us_location, make_id, offset_paginate

BASE_URL = "https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

MAX_PAGES = 20
LIMIT = 20


def fetch(company: dict) -> list[dict]:
    tenant = company["tenant"]
    site = company["site"]
    host = company.get("host", "wd5")  # Workday pod, e.g. wd1/wd5; defaults to wd5
    url = BASE_URL.format(tenant=tenant, site=site, host=host)
    jobs = []

    def fetch_page(offset: int) -> tuple[list, int]:
        payload = {
            "appliedFacets": {},
            "limit": LIMIT,
            "offset": offset,
            "searchText": "intern",
        }
        try:
            resp = http_post(url, json=payload, headers=HEADERS)
        except Exception as e:
            raise RuntimeError(f"Workday fetch failed for {company['name']}: {e}")
        data = resp.json()
        return data.get("jobPostings", []), data.get("total", 0)

    for postings in offset_paginate(fetch_page, LIMIT, MAX_PAGES, company["name"]):
        for job in postings:
            title = job.get("title", "")
            if not is_relevant(title):
                continue

            external_path = job.get("externalPath", "")
            job_id = external_path.split("/")[-1]
            job_url = f"https://{host}.myworkdayjobs.com{external_path}" if external_path else ""
            location = job.get("locationsText", "")

            if not is_us_location(location):
                continue

            jobs.append({
                "id": job_id or make_id(company["name"], title, job_url),
                "company": company["name"],
                "title": title,
                "url": job_url,
                "location": location,
            })

    return jobs
