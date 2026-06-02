import requests

from fetchers import is_relevant, is_us_location, make_id

# Workday uses a standardized jobs endpoint across tenants.
# We POST a search query and page through results.
BASE_URL = "https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def fetch(company: dict) -> list[dict]:
    tenant = company["tenant"]
    site = company["site"]
    url = BASE_URL.format(tenant=tenant, site=site)

    jobs = []
    offset = 0
    limit = 20

    while True:
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "intern",
        }

        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Workday fetch failed for {company['name']}: {e}")

        data = resp.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            title = job.get("title", "")
            if not is_relevant(title):
                continue

            # externalPath already contains the full path (e.g. /tenant/site/job/Title_ID)
            external_path = job.get("externalPath", "")
            job_id = external_path.split("/")[-1]
            job_url = f"https://wd5.myworkdayjobs.com{external_path}" if external_path else ""
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

        total = data.get("total", 0)
        offset += limit
        if offset >= total:
            break

    return jobs
