import json
import os
import re
import time

import requests
from google import genai

from fetchers import KEYWORD_RE, http_get, make_id, record_truncation

# Gemini 3.5 Flash-Lite (GA) — low-latency, low-cost, built for high-volume
# extraction work like this. Bump this constant to change models.
GEMINI_MODEL = "gemini-3.5-flash-lite"

JINA_BASE = "https://r.jina.ai/"
JINA_BALANCE_URL = "https://embeddings-dashboard-api.jina.ai/api/v1/api_key/user"
CONTENT_LIMIT = 40000  # per-chunk size; ~10k tokens, well inside Flash-Lite's 1M window
MAX_CHUNKS = 4         # caps cost at 4 Gemini calls (~160k chars) for one company
OVERLAP = 2000         # chunk overlap so a posting on a boundary survives in one slice

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
    # Note: _fetch_via_jina escalates auth tiers process-wide (see _TIERS below),
    # so a rate limit hit here changes which key every *subsequent* company uses.
    page_content = _fetch_via_jina(company["url"])
    raw_jobs = _extract_all_chunks(page_content, company["url"], company["name"])
    return _normalize(raw_jobs, company["name"])


def _normalize(raw_jobs: list[dict], company_name: str) -> list[dict]:
    """Coerce Gemini's extracted objects into the shared job shape.

    Split out from `fetch` so the drop conditions below are testable without
    making a Jina request and a Gemini call.
    """
    jobs = []
    dropped = 0
    for job in raw_jobs:
        title = job.get("title", "").strip()
        url = job.get("url", "").strip()
        location = job.get("location", "").strip()

        if not title or not url:
            dropped += 1
            continue

        jobs.append({
            "id": make_id(company_name, title, url),
            "company": company_name,
            "title": title,
            "url": url,
            "location": location,
        })

    if dropped:
        record_truncation(
            company_name,
            f"{dropped} extracted posting(s) discarded for missing title or url",
        )

    return jobs


# Jina Reader auth tiers, tried cheapest-first. Tier 0 is the keyless free tier
# (no Authorization header); we only climb to a paid key when the current tier
# stops working. Escalation is one-way and process-wide: once a tier fails we
# stay on the next one for every remaining company, rather than re-probing a
# rate-limited or exhausted tier on each fetch.
#
#   free  → rate-limited / repeatedly failing  → key 1
#   key 1 → exhausted (HTTP 402)               → key 2
#   key 2 → exhausted (HTTP 402)               → hard fail
#
# A tier whose env var is unset is skipped (e.g. JINA_API_KEY empty → free falls
# straight through to key 2).
_TIERS = (
    {"label": "free", "env": None},
    {"label": "key 1", "env": "JINA_API_KEY"},
    {"label": "key 2", "env": "JINA_API_KEY_FALLBACK"},
)

_tier_index = 0
# label -> api_key, populated only for key tiers we actually fetched with, so the
# email footer can report balances for exactly the keys this run consumed.
_used_keys: dict[str, str] = {}


def _remaining_tokens(api_key: str) -> int | None:
    """Return the remaining Jina token balance for `api_key`, or None if unavailable.

    Queries the (undocumented) dashboard endpoint the 'API Key & Billing' tab uses.
    Best-effort only: any network, auth, or shape error yields None so callers can
    skip reporting rather than fail, but the reason is logged so a broken read is
    diagnosable instead of silently vanishing.
    """
    try:
        resp = requests.get(JINA_BALANCE_URL, params={"api_key": api_key}, timeout=15)
        resp.raise_for_status()
        # `total_balance` is the remaining balance (trial_balance + regular_balance).
        return resp.json().get("wallet", {}).get("total_balance")
    except Exception as e:
        print(f"[WARN] Jina balance lookup failed: {e}")
        return None


def usage_summary() -> list[dict]:
    """Return remaining-token balances for the keys this run actually used.

    Each entry is {"label": str, "remaining": int}. A key is reported only if it
    was used to fetch at least one page (so a free-tier-only run reports nothing)
    and its balance can currently be read. Never raises.
    """
    summary = []
    for tier in _TIERS:
        label = tier["label"]
        api_key = _used_keys.get(label)
        if not api_key:
            continue
        remaining = _remaining_tokens(api_key)
        if remaining is not None:
            summary.append({"label": label, "remaining": remaining})
    return summary


def _tier_headers(api_key: str) -> dict:
    """Build Reader headers, authenticating only when a key is present."""
    headers = {"Accept": "text/plain"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _is_exhausted(exc: Exception) -> bool:
    """True when `exc` is Jina's 402 (token balance spent) response."""
    return (
        isinstance(exc, requests.HTTPError)
        and exc.response is not None
        and exc.response.status_code == 402
    )


def _get_with_failover(url: str) -> requests.Response:
    """Fetch `url` via Jina Reader, climbing auth tiers as each stops working.

    The free tier is best-effort: any failure after ``http_get``'s built-in retries
    (rate limits, 5xx, network errors) escalates to the next configured key. A paid
    key is only abandoned when it 402s (balance exhausted); any other error on a key
    is a genuine fetch failure and is raised. Escalation persists across companies
    via ``_tier_index`` so we never re-probe a spent tier.
    """
    global _tier_index

    jina_url = JINA_BASE + url
    last_exc: Exception | None = None

    while _tier_index < len(_TIERS):
        tier = _TIERS[_tier_index]
        api_key = os.getenv(tier["env"], "") if tier["env"] else ""

        # A key tier with no key configured can't be used — skip to the next.
        if tier["env"] and not api_key:
            _tier_index += 1
            continue

        try:
            resp = http_get(jina_url, headers=_tier_headers(api_key), timeout=30)
            if api_key:
                _used_keys[tier["label"]] = api_key
            return resp
        except Exception as e:
            last_exc = e
            on_free_tier = tier["env"] is None

            if on_free_tier:
                # Free tier gave out — record nothing (no key spent) and climb.
                print(f"[WARN] Jina free tier failed for {url} ({e}) — escalating to a key")
                _tier_index += 1
                continue

            # We reached this tier, so its key was engaged for the run.
            _used_keys[tier["label"]] = api_key
            if _is_exhausted(e):
                print(f"[WARN] Jina {tier['label']} exhausted (402) — escalating")
                _tier_index += 1
                continue

            # Non-exhaustion error on a paid key: a real failure, not a reason to burn the next key.
            raise RuntimeError(f"Jina fetch failed for {url} on {tier['label']}: {e}")

    raise RuntimeError(f"Jina fetch failed for {url}: all auth tiers exhausted ({last_exc})")


def _fetch_via_jina(url: str) -> str:
    return _get_with_failover(url).text


def _chunk(content: str, url: str) -> list[str]:
    """Split page content into overlapping slices, one per Gemini call.

    Previously the content past CONTENT_LIMIT was simply discarded, which silently
    lost postings on any long careers page. Splitting instead costs one extra
    Gemini call per slice, which is far cheaper than missing listings.

    Slices overlap by OVERLAP chars so a posting straddling a boundary is intact in
    at least one of them; the duplicates that creates are removed by id afterwards.
    """
    if len(content) <= CONTENT_LIMIT:
        return [content]

    chunks = []
    start = 0
    covered = 0
    while start < len(content) and len(chunks) < MAX_CHUNKS:
        end = start + CONTENT_LIMIT
        if end < len(content):
            # Prefer a newline boundary, but only if it is not so far back that it
            # wastes the slice — some pages embed huge single-line blobs.
            nl = content.rfind("\n", start + int(CONTENT_LIMIT * 0.9), end)
            if nl > start:
                end = nl
        chunks.append(content[start:end])
        covered = end
        if end >= len(content):
            break
        start = end - OVERLAP

    if covered < len(content):
        record_truncation(
            url,
            f"content is {len(content)} chars; only the first {covered} were scanned "
            f"across {MAX_CHUNKS} chunks — postings beyond that point will be missed",
        )

    return chunks


def _call_gemini_with_retry(prompt: str, company_name: str) -> str:
    """Send `prompt` to Gemini; retry with backoff on rate-limit and transient errors."""
    client = _get_gemini_client()
    last_exc: Exception | None = None
    attempts = 4

    for attempt in range(attempts):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            last_exc = e
            if attempt < attempts - 1 and _is_transient(e):
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                reason = "Rate limited" if _is_rate_limit(e) else f"Transient error ({e})"
                print(f"[{company_name}] {reason} — retrying in {wait}s")
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


def _extract_all_chunks(content: str, url: str, company_name: str) -> list[dict]:
    """Run extraction over every chunk of the page and merge the results.

    One Gemini call per chunk. Duplicates from the chunk overlap are dropped on
    (title, url), keeping the first occurrence.
    """
    chunks = _chunk(content, url)

    # Skip chunks that cannot possibly contain a match before paying for a Gemini
    # call. The extraction prompt requires the job *title* to contain Intern /
    # Internship / Co-op, so a slice without any of those words anywhere in it —
    # nav, cookie banners, footers, embedded theme JSON — has nothing to find.
    # This is a keyword presence test, not a relevance judgement: anything that
    # merely mentions the words is still sent on for Gemini to decide.
    keepers = [c for c in chunks if KEYWORD_RE.search(c)]
    skipped = len(chunks) - len(keepers)
    if len(chunks) > 1 or skipped:
        print(
            f"[{company_name}] {len(chunks)} chunk(s), "
            f"{len(keepers)} sent to Gemini, {skipped} skipped as keyword-free"
        )

    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for chunk in keepers:
        for job in _extract_via_gemini(chunk, company_name):
            key = (job.get("title", "").strip(), job.get("url", "").strip())
            if key in seen:
                continue
            seen.add(key)
            merged.append(job)

    return merged


def _extract_via_gemini(content: str, company_name: str) -> list[dict]:
    """Orchestrate Gemini extraction: build prompt → call API → parse response."""
    prompt = EXTRACTION_PROMPT.format(content=content)
    raw_text = _call_gemini_with_retry(prompt, company_name)
    return _parse_gemini_response(raw_text, company_name)


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "rate" in msg


# Transient transport/server failures worth another attempt. Large prompts (the
# multi-chunk companies) are the ones that get their connection dropped mid-flight.
_TRANSIENT_MARKERS = (
    "server disconnected",
    "connection reset",
    "connection aborted",
    "connection error",
    "remote protocol error",
    "read timeout",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "internal error",
    "deadline exceeded",
    "500",
    "502",
    "503",
    "504",
)


def _is_transient(e: Exception) -> bool:
    """True when the failure looks like a network/server blip rather than a bad request."""
    if _is_rate_limit(e):
        return True
    msg = str(e).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)
