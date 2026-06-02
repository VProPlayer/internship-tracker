import re
import requests

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

# Word-boundary patterns — prevents matching "internal" / "international"
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
    return bool(_KEYWORD_RE.search(t)) and not any(ex in t for ex in EXCLUDE_KEYWORDS)
