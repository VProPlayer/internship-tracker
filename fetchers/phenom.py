from fetchers import http_get, is_relevant, offset_paginate

SEARCH_PATH = "/api/pcsx/search"
PAGE_SIZE = 100
MAX_PAGES = 10


def fetch(company: dict) -> list[dict]:
    api_base = company["api_base"].rstrip("/")
    domain = company["domain"]
    url = api_base + SEARCH_PATH
    title_exclude = [t.lower() for t in company.get("title_exclude", [])]
    jobs = []

    def fetch_page(start: int) -> tuple[list, int]:
        params = {
            "domain": domain,
            "query": "intern",
            "location": "United States",
            "start": start,
            "num": PAGE_SIZE,
        }
        try:
            resp = http_get(url, params=params)
        except Exception as e:
            raise RuntimeError(f"Phenom fetch failed for {company['name']}: {e}")
        data = resp.json()
        positions = data.get("data", {}).get("positions", [])
        total = data.get("data", {}).get("count", 0)
        return positions, total

    for positions in offset_paginate(fetch_page, PAGE_SIZE, MAX_PAGES, company["name"]):
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

    return jobs
