import hashlib
import json
import os
import re
import time

import google.generativeai as genai
import requests

JINA_BASE = "https://r.jina.ai/"

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

        if not title:
            continue

        job_id = _make_id(company["name"], title, url)
        jobs.append({
            "id": job_id,
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

    # Trim to ~12k chars to stay within Gemini token limits
    return resp.text[:12000]


def _extract_via_gemini(content: str, company_name: str) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.1-flash-lite")

    prompt = EXTRACTION_PROMPT.format(content=content)

    try:
        time.sleep(4)
        response = model.generate_content(prompt)
        text = response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini extraction failed for {company_name}: {e}")

    # Strip markdown code fences if Gemini wraps the output
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Gemini occasionally returns partial JSON — log and return empty
        print(f"[{company_name}] Gemini returned non-JSON: {text[:200]}")
        return []


def _make_id(company: str, title: str, url: str) -> str:
    raw = f"{company}{title}{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
