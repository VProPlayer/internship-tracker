import hashlib
import re
from collections.abc import Callable, Generator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Location filtering ────────────────────────────────────────────────────────

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

_US_TERMS = ("united states", "usa", "u.s.a", "u.s.")

# Matches "Remote", "Hybrid", "Remote - US", "Remote/USA" etc. — but NOT
# "Remote EMEA", "Hybrid, London, UK" since those have non-US context after.
_REMOTE_STANDALONE_RE = re.compile(
    r'^(?:remote|hybrid|virtual|work\s+from\s+home|wfh|anywhere)'
    r'(?:\s*[-–/]?\s*(?:us|usa|u\.s\.a?|united\s+states))?$',
    re.IGNORECASE,
)

_STATE_RE = re.compile(r',\s*([A-Z]{2})(?:\s+\d{5})?(?:\s*$|,)', re.IGNORECASE)


def is_us_location(location: str) -> bool:
    """Return True if location is US-based, explicitly remote/hybrid, or unknown."""
    if not location:
        return True
    loc = location.strip()
    if _REMOTE_STANDALONE_RE.match(loc):
        return True
    loc_lower = loc.lower()
    if any(term in loc_lower for term in _US_TERMS):
        return True
    m = _STATE_RE.search(loc)
    if m and m.group(1).upper() in _US_STATES:
        return True
    return False


# ── Job relevance filtering ───────────────────────────────────────────────────

KEYWORD_RE = re.compile(
    r'\bintern(?:ship)?s?\b|\bco-?op\b|\bstudent\b',
    re.IGNORECASE,
)

_EXCLUDE_RE = re.compile(
    r'\b(?:'
    r'ph\.?d|doctoral|doctorate|postdoc|post-doc|'
    r'graduate\s+research|ms\s+intern|masters\s+intern|mba\s+intern|'
    r'graduate\s+intern|grad\s+intern|m\.?eng|'
    r'senior|sr\.|staff|director|manager|principal|head\s+of|'
    r'vice\s+president|account\s+executive|accountant|'
    r'project\s+planner|program\s+manager|operations\s+specialist|lead'
    r')\b',
    re.IGNORECASE,
)


def is_relevant(title: str) -> bool:
    return bool(KEYWORD_RE.search(title)) and not bool(_EXCLUDE_RE.search(title))


# ── Stable ID generation ──────────────────────────────────────────────────────

def make_id(company: str, title: str, url: str) -> str:
    return hashlib.sha256(f"{company}{title}{url}".encode()).hexdigest()[:16]


# ── HTTP helpers with automatic retry ────────────────────────────────────────

def _build_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


_session = _build_session()


def http_get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 15)
    resp = _session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def http_post(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 15)
    resp = _session.post(url, **kwargs)
    resp.raise_for_status()
    return resp


# ── Offset pagination helper ──────────────────────────────────────────────────

def offset_paginate(
    fetch_page: Callable[[int], tuple[list, int]],
    page_size: int,
    max_pages: int,
    company_name: str,
) -> Generator[list, None, None]:
    """Yield each page of results from an offset-paginated API endpoint."""
    offset = 0
    for _ in range(max_pages):
        items, total = fetch_page(offset)
        if not items:
            return
        yield items
        offset += page_size
        if offset >= total:
            return
    print(f"[WARN] {company_name}: hit max_pages ({max_pages}) — some postings may be missed")
