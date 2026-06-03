from fetchers import http_get, is_relevant, is_us_location

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch(company: dict) -> list[dict]:
    url = BASE_URL.format(slug=company["slug"])

    try:
        resp = http_get(url)
    except Exception as e:
        raise RuntimeError(f"Greenhouse fetch failed for {company['name']}: {e}")

    data = resp.json()
    jobs = []

    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not is_relevant(title):
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
