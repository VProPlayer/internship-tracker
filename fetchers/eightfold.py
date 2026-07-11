from fetchers import http_get, is_relevant, is_us_location, make_id, offset_paginate

SEARCH_PATH = "/api/apply/v2/jobs"
PAGE_SIZE = 10
MAX_PAGES = 40


def fetch(company: dict) -> list[dict]:
    host = company["host"].rstrip("/")
    domain = company["domain"]
    url = f"https://{host}{SEARCH_PATH}"
    jobs = []

    def fetch_page(start: int) -> tuple[list, int]:
        params = {
            "domain": domain,
            "query": "intern",
            "start": start,
            "num": PAGE_SIZE,
        }
        try:
            resp = http_get(url, params=params)
        except Exception as e:
            raise RuntimeError(f"Eightfold fetch failed for {company['name']}: {e}")
        data = resp.json()
        positions = data.get("positions", [])
        total = data.get("count", 0)
        return positions, total

    for positions in offset_paginate(fetch_page, PAGE_SIZE, MAX_PAGES, company["name"]):
        for pos in positions:
            title = pos.get("name", "")
            if not is_relevant(title):
                continue

            location = pos.get("location", "")
            if not is_us_location(location):
                continue

            job_url = pos.get("canonicalPositionUrl", "")

            job_id = pos.get("id")
            jobs.append({
                "id": str(job_id) if job_id is not None else make_id(company["name"], title, job_url),
                "company": company["name"],
                "title": title,
                "url": job_url,
                "location": location,
            })

    return jobs
