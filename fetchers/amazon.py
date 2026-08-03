from fetchers import http_get, is_relevant, is_us_country, labeled_errors, make_id, offset_paginate

BASE_URL = "https://www.amazon.jobs/en/search.json"
LIMIT = 100
MAX_PAGES = 10


def fetch(company: dict) -> list[dict]:
    jobs = []

    def fetch_page(offset: int) -> tuple[list, int]:
        params = {
            "base_query": "intern",
            "country[]": "United+States",
            "is_intern[]": "1",
            "result_limit": LIMIT,
            "offset": offset,
        }
        with labeled_errors("Amazon", company["name"]):
            resp = http_get(BASE_URL, params=params)
        data = resp.json()
        return data.get("jobs", []), data.get("hits", 0)

    for postings in offset_paginate(fetch_page, LIMIT, MAX_PAGES, company["name"]):
        for job in postings:
            if not is_us_country(job.get("country_code", "")):
                continue

            title = job.get("title", "")
            if not is_relevant(title):
                continue

            job_path = job.get("job_path", "")
            url = f"https://www.amazon.jobs{job_path}" if job_path else ""

            city = job.get("city", "")
            state = job.get("state", "")
            location = f"{city}, {state}".strip(", ") if (city or state) else job.get("location", "")

            jobs.append({
                "id": str(job.get("id") or job.get("id_icims") or make_id(company["name"], title, url)),
                "company": company["name"],
                "title": title,
                "url": url,
                "location": location,
            })

    return jobs
