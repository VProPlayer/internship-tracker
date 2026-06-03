from fetchers import http_get, is_relevant, is_us_location

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_handle}"


def fetch(company: dict) -> list[dict]:
    url = BASE_URL.format(board_handle=company["board_handle"])

    try:
        resp = http_get(url)
    except Exception as e:
        raise RuntimeError(f"Ashby fetch failed for {company['name']}: {e}")

    data = resp.json()
    jobs = []

    for posting in data.get("jobs", []):
        title = posting.get("title", "")
        if not is_relevant(title):
            continue

        location = posting.get("location", "")

        # Use structured country data when available; fall back to location string
        address = posting.get("address") or {}
        postal = address.get("postalAddress") or {}
        country = postal.get("addressCountry", "")

        if country:
            is_us = country.lower() in ("united states", "us", "usa")
        else:
            is_us = posting.get("isRemote") is True or is_us_location(location)

        if not is_us:
            continue

        jobs.append({
            "id": posting["id"],
            "company": company["name"],
            "title": title,
            "url": posting.get("jobUrl", ""),
            "location": location,
        })

    return jobs
