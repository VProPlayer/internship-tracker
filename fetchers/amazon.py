import requests

from fetchers import is_relevant

BASE_URL = "https://www.amazon.jobs/en/search.json"
LIMIT = 100
MAX_PAGES = 10  # cap at 1000 jobs


def fetch(company: dict) -> list[dict]:
    jobs = []
    offset = 0

    for _ in range(MAX_PAGES):
        params = {
            "base_query": "intern",
            "country[]": "United+States",
            "is_intern[]": "1",
            "result_limit": LIMIT,
            "offset": offset,
        }

        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Amazon fetch failed: {e}")

        data = resp.json()
        postings = data.get("jobs", [])
        if not postings:
            break

        for job in postings:
            # Double-check country in case API filter leaks non-US results
            if job.get("country_code", "").upper() not in ("US", "USA", "UNITED STATES"):
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
                "id": str(job.get("id") or job.get("id_icims", "")),
                "company": company["name"],
                "title": title,
                "url": url,
                "location": location,
            })

        total = data.get("hits", 0)
        offset += LIMIT
        if offset >= total:
            break

    return jobs
