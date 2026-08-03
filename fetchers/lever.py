from fetchers import http_get, is_relevant, is_us_country, is_us_location, labeled_errors, make_id

BASE_URL = "https://api.lever.co/v0/postings/{handle}?mode=json"


def fetch(company: dict) -> list[dict]:
    url = BASE_URL.format(handle=company["handle"])

    with labeled_errors("Lever", company["name"]):
        resp = http_get(url)

    jobs = []

    for posting in resp.json():
        title = posting.get("text", "")
        if not is_relevant(title):
            continue

        categories = posting.get("categories") or {}
        location = categories.get("location", "")

        # Prefer the structured country code; fall back to the location string
        country = posting.get("country", "")
        if country:
            is_us = is_us_country(country)
        else:
            is_us = is_us_location(location)

        if not is_us:
            continue

        job_url = posting.get("hostedUrl", "")
        jobs.append({
            "id": posting.get("id") or make_id(company["name"], title, job_url),
            "company": company["name"],
            "title": title,
            "url": job_url,
            "location": location,
        })

    return jobs
