import hashlib
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager

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


# Every spelling of "United States" seen across the ATS platforms we fetch from:
# two-letter codes (Lever), three-letter codes (Amazon), and full names (Ashby).
# Compared after stripping case and periods, so "U.S." and "us" both match.
_US_COUNTRY_VALUES = {"us", "usa", "united states", "united states of america"}


def is_us_country(country: str) -> bool:
    """Return True if an ATS `country` field denotes the United States.

    Each fetcher previously carried its own tuple of accepted spellings, and they
    had drifted — some omitted "United States", so a platform that spells the
    country out would have had every US posting silently dropped.
    """
    return country.strip().lower().replace(".", "") in _US_COUNTRY_VALUES


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
        status_forcelist=[401, 429, 500, 502, 503, 504],
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


@contextmanager
def labeled_errors(what: str, company_name: str, detail: str = ""):
    """Re-raise any exception from the block as a RuntimeError naming the company.

    Every fetcher wrapped its first HTTP call in an identical try/except purely to
    attach this label; `http_get`/`http_post` already handle retries and status.
    """
    try:
        yield
    except RuntimeError:
        raise
    except Exception as e:
        suffix = f" ({detail})" if detail else ""
        raise RuntimeError(f"{what} fetch failed for {company_name}{suffix}: {e}") from e


# ── Truncation reporting ──────────────────────────────────────────────────────

# Fetchers cannot raise on truncation without discarding the postings they already
# collected, so they record it here instead and `main.py` drains this after each
# company. Previously this was a bare `print`, which never reached the failure email.
_truncations: list[str] = []


def record_truncation(company_name: str, detail: str) -> None:
    msg = f"{company_name}: {detail}"
    print(f"[WARN] {msg}")
    _truncations.append(msg)


def drain_truncations() -> list[str]:
    """Return truncations recorded since the last drain, and clear them."""
    drained = list(_truncations)
    _truncations.clear()
    return drained


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
    record_truncation(
        company_name,
        f"hit max_pages ({max_pages}) — postings beyond {max_pages * page_size} were not fetched",
    )
