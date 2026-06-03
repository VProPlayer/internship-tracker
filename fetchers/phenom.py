import requests

from fetchers import is_relevant

# Phenom People PCSX search API — used by Microsoft, Qualcomm, and others.
# Each company exposes it at their own subdomain with a domain= param.
SEARCH_PATH = "/api/pcsx/search"
PAGE_SIZE = 100
MAX_PAGES = 10  # cap at 1000 positions


def fetch(company: dict) -> list[dict]:
    api_base = company["api_base"].rstrip("/")
    domain = company["domain"]
    url = api_base + SEARCH_PATH

    jobs = []
    start = 0
    title_exclude = [t.lower() for t in company.get("title_exclude", [])]

    for _ in range(MAX_PAGES):
        params = {
            "domain": domain,
            "query": "intern",
            "location": "United States",
            "start": start,
            "num": PAGE_SIZE,
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Phenom fetch failed for {company['name']}: {e}")

        data = resp.json()
        positions = data.get("data", {}).get("positions", [])
        if not positions:
            break

        for pos in positions:
            title = pos.get("name", "")
            if not is_relevant(title):
                continue

            if title_exclude and any(excl in title.lower() for excl in title_exclude):
                continue

            locations = pos.get("standardizedLocations") or pos.get("locations") or []
            is_us = any(
                loc.endswith(", US") or "united states" in loc.lower()
                for loc in locations
            )
            if not is_us:
                continue

            position_url = pos.get("positionUrl", "")
            job_url = f"{api_base}{position_url}" if position_url else ""
            location = locations[0] if locations else ""

            jobs.append({
                "id": str(pos["id"]),
                "company": company["name"],
                "title": title,
                "url": job_url,
                "location": location,
            })

        total = data.get("data", {}).get("count", 0)
        start += PAGE_SIZE
        if start >= total:
            break

    return jobs
