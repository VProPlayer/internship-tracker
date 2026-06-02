import json
import os
import re
import time

from google import genai
import requests

from fetchers import make_id

JINA_BASE = "https://r.jina.ai/"
CONTENT_LIMIT = 12000

EXTRACTION_PROMPT = """
You are extracting internship job postings from the text of a company careers page.

A posting counts as a match ONLY if ALL of the following are true:
1. The job title explicitly contains "Intern", "Internship", or "Co-op" (or "Coop").
2. It is targeted at undergraduate (BS/BA) students — NOT graduate, MS, PhD, or MBA students.
3. It is in a technical field: software engineering, machine learning, AI, data science,
   data engineering, hardware engineering, IT, systems, or research at the undergrad level.
4. The location is in the United States, or the role is remote and open to US applicants.

Exclude ALL of the following — even if the title contains "intern" or "co-op":
- Roles with seniority prefixes: Senior, Staff, Principal, Lead, Director, Manager, Head of, VP, Sr.
- Full-time roles (no "intern" or "co-op" in the title)
- PhD intern, doctoral intern, graduate intern, grad intern, MS intern, masters intern, MBA intern
- Roles requiring a master's or PhD as minimum or preferred qualification
- Non-technical roles: finance, accounting, HR, marketing, legal, communications, operations
- Roles located entirely outside the United States

When in doubt about level, EXCLUDE it.
When in doubt about location, EXCLUDE it.

Return a JSON array of objects with keys: title, url, location.
Return an empty array [] if no matching postings are found.
Return ONLY the JSON array — no markdown, no explanation, no code fences.

Careers page content:
{content}
"""


def fetch(company: dict) -> list[dict]:
    page_content = _fetch_via_jina(company["url"])
    raw_jobs = _extract_via_gemini(page_content, company["name"])

    jobs = []
    for job in raw_jobs:
        title = job.get("title", "").strip()
        url = job.get("url", "").strip()
        location = job.get("location", "").strip()

        if not title or not url:
            continue

        jobs.append({
            "id": make_id(company["name"], title, url),
            "company": company["name"],
            "title": title,
            "url": url,
            "location": location,
        })

    return jobs


def _fetch_via_jina(url: str) -> str:
    jina_url = JINA_BASE + url
    headers = {"Accept": "text/plain"}

    api_key = os.getenv("JINA_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(jina_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Jina fetch failed for {url}: {e}")

    content = resp.text
    if len(content) > CONTENT_LIMIT:
        print(f"[WARN] {url}: content truncated from {len(content)} to {CONTENT_LIMIT} chars — late postings may be missed")
        content = content[:CONTENT_LIMIT]

    return content


def _extract_via_gemini(content: str, company_name: str) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    prompt = EXTRACTION_PROMPT.format(content=content)

    last_exc = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )
            text = response.text.strip()
            break
        except Exception as e:
            last_exc = e
            if attempt < 2 and _is_rate_limit(e):
                wait = 5 * (2 ** attempt)  # 5s, 10s
                print(f"[{company_name}] Rate limited — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Gemini extraction failed for {company_name}: {e}")
    else:
        raise RuntimeError(f"Gemini extraction failed for {company_name}: {last_exc}")

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[{company_name}] Gemini returned non-JSON: {text[:200]}")
        return []


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "rate" in msg
