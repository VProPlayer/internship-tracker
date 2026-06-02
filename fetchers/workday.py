import re
import requests

# Workday uses a standardized jobs endpoint across tenants.
# We POST a search query and page through results.
BASE_URL = "https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

_KEYWORD_RE = re.compile(
    r'\bintern(?:ship)?s?\b|\bco-?op\b',
    re.IGNORECASE,
)

EXCLUDE_KEYWORDS = [
    # degree level
    "phd", "ph.d", "doctoral", "doctorate", "postdoc", "post-doc",
    "graduate research", "ms intern", "masters intern", "mba intern",
    "graduate intern", "grad intern", "meng", "m.eng",
    # seniority / non-intern roles
    "senior", "staff", "director", "manager", "head of", "principal",
    "vice president", "account executive", "accountant", "sr.",
    "project planner", "program manager", "operations specialist",
    "specialist", "lead,", ", lead",
]

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
            if not _is_relevant(title):
                continue

            job_id = job.get("externalPath", "").split("/")[-1]
            job_url = f"https://wd5.myworkdayjobs.com/{tenant}/{site}/job/{job.get('externalPath', '').lstrip('/')}"
            location = job.get("locationsText", "")

            jobs.append({
                "id": job_id or _fallback_id(company["name"], title, job_url),
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


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return bool(_KEYWORD_RE.search(t)) and not any(ex in t for ex in EXCLUDE_KEYWORDS)


def _fallback_id(company: str, title: str, url: str) -> str:
    import hashlib
    raw = f"{company}{title}{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
