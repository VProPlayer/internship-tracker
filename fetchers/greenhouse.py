import requests

from fetchers import EXCLUDE_KEYWORDS, KEYWORD_RE, is_us_location

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch(company: dict) -> list[dict]:
    slug = company["slug"]
    url = BASE_URL.format(slug=slug)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Greenhouse fetch failed for {company['name']}: {e}")

    data = resp.json()
    jobs = []

    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not _is_relevant(title):
            continue

        location = ""
        offices = job.get("offices", [])
        if offices:
            location = offices[0].get("name", "")

        if not is_us_location(location):
            continue

        jobs.append({
            "id": str(job["id"]),
            "company": company["name"],
            "title": title,
            "url": job.get("absolute_url", ""),
            "location": location,
        })

    return jobs


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return bool(KEYWORD_RE.search(t)) and not any(ex in t for ex in EXCLUDE_KEYWORDS)
