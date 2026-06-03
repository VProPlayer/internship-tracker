import json
import os
import re
import time

from google import genai

from fetchers import http_get, make_id

JINA_BASE = "https://r.jina.ai/"
CONTENT_LIMIT = 40000  # raised from 12k; Gemini flash handles ~1M tokens so 40k chars (~10k tokens) is well within range

EXTRACTION_PROMPT = """
You are extracting internship job postings from the text of a company careers page.

A posting counts as a match ONLY if ALL of the following are true:
1. The job title explicitly contains "Intern", "Internship", or "Co-op" (or "Coop").
2. It is targeted at undergraduate (BS/BA) students — NOT graduate, MS, PhD, or MBA students.
3. It is in a technical field: software engineering, machine learning, AI, data science,
   data engineering, hardware engineering, IT, systems, or research at the undergrad level.
4. The location is in the United States, or the role is remote and open to US applicants.
5. The posting is currently OPEN and accepting applications right now.

Exclude ALL of the following — even if the title contains "intern" or "co-op":
- Roles with seniority prefixes: Senior, Staff, Principal, Lead, Director, Manager, Head of, VP, Sr.
- Full-time roles (no "intern" or "co-op" in the title)
- PhD intern, doctoral intern, graduate intern, grad intern, MS intern, masters intern, MBA intern
- Roles requiring a master's or PhD as minimum or preferred qualification
- Non-technical roles: finance, accounting, HR, marketing, legal, communications, operations
- Roles located entirely outside the United States
- Program descriptions, internship category overviews, or "coming soon" placeholders —
  these are NOT job postings even if they have "internship" in the heading
- Any posting on a page that says the application period is closed, applications are not
  being accepted, or positions are unavailable at this time — return [] for the entire page

The "url" field must be a direct, specific link to the individual job posting page.
Do NOT use the careers home page URL, a talent community sign-up link, an anchor (#),
or any URL that is not a dedicated page for that exact job.
If no direct job URL is available for a posting, exclude it entirely.

Return a JSON array of objects with keys: title, url, location.
Return an empty array [] if no matching postings are found.
Return ONLY the JSON array — no markdown, no explanation, no code fences.

Careers page content:
{content}
"""

_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    """Return a cached Gemini client, initializing it once per process."""
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


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
        resp = http_get(jina_url, headers=headers, timeout=30)
    except Exception as e:
        raise RuntimeError(f"Jina fetch failed for {url}: {e}")

    content = resp.text
    if len(content) > CONTENT_LIMIT:
        # Truncate at the last newline before the limit so we never cut mid-line
        cutoff = content.rfind("\n", 0, CONTENT_LIMIT)
        cutoff = cutoff if cutoff > 0 else CONTENT_LIMIT
        print(
            f"[WARN] {url}: content truncated from {len(content)} to {cutoff} chars "
            f"— postings beyond that point will be missed"
        )
        content = content[:cutoff]

    return content


def _call_gemini_with_retry(prompt: str, company_name: str) -> str:
    """Send `prompt` to Gemini; retry up to 3 times with backoff on rate-limit errors."""
    client = _get_gemini_client()
    last_exc: Exception | None = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            last_exc = e
            if attempt < 2 and _is_rate_limit(e):
                wait = 5 * (2 ** attempt)  # 5s, 10s
                print(f"[{company_name}] Rate limited — retrying in {wait}s")
                time.sleep(wait)
            else:
                break

    raise RuntimeError(f"Gemini extraction failed for {company_name}: {last_exc}")


def _parse_gemini_response(text: str, company_name: str) -> list[dict]:
    """Strip optional markdown fences and parse the JSON array from a Gemini response."""
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[{company_name}] Gemini returned non-JSON: {text[:200]}")
        return []


def _extract_via_gemini(content: str, company_name: str) -> list[dict]:
    """Orchestrate Gemini extraction: build prompt → call API → parse response."""
    prompt = EXTRACTION_PROMPT.format(content=content)
    raw_text = _call_gemini_with_retry(prompt, company_name)
    return _parse_gemini_response(raw_text, company_name)


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "rate" in msg
