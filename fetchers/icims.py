import requests

from fetchers import is_relevant, is_us_location, make_id

# iCIMS exposes a REST API. We use the /search endpoint with a keyword filter.
SEARCH_TEMPLATE = "{base}/search?ql=jobtitle%3D%22intern%22+OR+jobtitle%3D%22co-op%22&icalinternal=0&ss=1&in_iframe=1"

HEADERS = {
    "Accept": "application/json",
}


def fetch(company: dict) -> list[dict]:
    base_url = company["url"].rstrip("/")
    search_url = SEARCH_TEMPLATE.format(base=base_url)

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"iCIMS fetch failed for {company['name']}: {e}")

    data = resp.json()
    jobs = []

    items = data.get("searchResults", data.get("items", []))
    for item in items:
        title = item.get("jobtitle") or item.get("title", "")
        job_url = item.get("detailUrl") or item.get("url", "")

        if not title or not job_url:
            continue

        if not is_relevant(title):
            continue

        location = item.get("joblocation") or item.get("location", "")

        if not is_us_location(location):
            continue

        job_id = item.get("jobId") or item.get("id") or make_id(company["name"], title, job_url)

        jobs.append({
            "id": str(job_id),
            "company": company["name"],
            "title": title,
            "url": job_url,
            "location": location,
        })

    return jobs
