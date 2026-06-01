import requests

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

KEYWORDS = [
    "intern", "internship", "co-op", "coop", "new grad", "student"
]


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
    return any(kw in t for kw in KEYWORDS)
