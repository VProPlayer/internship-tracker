import hashlib
import requests

# iCIMS exposes a REST API. We use the /search endpoint with a keyword filter.
SEARCH_TEMPLATE = "{base}/search?ql=jobtitle%3D%22intern%22+OR+jobtitle%3D%22co-op%22&icalinternal=0&ss=1&in_iframe=1"

KEYWORDS = [
    "intern", "internship", "co-op", "coop", "student"
]

EXCLUDE_KEYWORDS = [
    "phd", "ph.d", "doctoral", "doctorate", "postdoc", "post-doc",
    "graduate research", "ms intern", "masters intern", "mba intern",
]

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
        title = item.get("jobtitle", item.get("title", ""))
        if not _is_relevant(title):
            continue

        job_url = item.get("detailUrl", item.get("url", ""))
        location = item.get("joblocation", item.get("location", ""))
        job_id = item.get("jobId", item.get("id", ""))

        if not job_id:
            job_id = _fallback_id(company["name"], title, job_url)

        jobs.append({
            "id": str(job_id),
            "company": company["name"],
            "title": title,
            "url": job_url,
            "location": location,
        })

    return jobs


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in KEYWORDS) and not any(ex in t for ex in EXCLUDE_KEYWORDS)


def _fallback_id(company: str, title: str, url: str) -> str:
    raw = f"{company}{title}{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
