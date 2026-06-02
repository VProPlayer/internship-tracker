import hashlib
import re

# ── Location filtering ────────────────────────────────────────────────────────

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

_US_TERMS = ("united states", "usa", "u.s.a", "u.s.", "remote", "hybrid")

_STATE_RE = re.compile(r',\s*([A-Z]{2})(?:\s+\d{5})?(?:\s*$|,)', re.IGNORECASE)


def is_us_location(location: str) -> bool:
    """Return True if location is US-based, remote, or unknown."""
    if not location:
        return True
    loc = location.strip().lower()
    if any(term in loc for term in _US_TERMS):
        return True
    m = _STATE_RE.search(location)
    if m and m.group(1).upper() in _US_STATES:
        return True
    return False


# ── Job relevance filtering (shared by Greenhouse, Workday, iCIMS) ────────────

KEYWORD_RE = re.compile(
    r'\bintern(?:ship)?s?\b|\bco-?op\b|\bstudent\b',
    re.IGNORECASE,
)

# Regex-based exclusion with word boundaries — avoids false negatives from bare
# substring matching (e.g. "specialist" no longer blocks "ML Specialist Intern";
# "lead" is matched as a standalone word, not via fragile comma heuristics).
_EXCLUDE_RE = re.compile(
    r'\b(?:'
    # degree / academic level
    r'ph\.?d|doctoral|doctorate|postdoc|post-doc|'
    r'graduate\s+research|ms\s+intern|masters\s+intern|mba\s+intern|'
    r'graduate\s+intern|grad\s+intern|m\.?eng|'
    # seniority & non-intern roles
    r'senior|sr\.|staff|director|manager|principal|head\s+of|'
    r'vice\s+president|account\s+executive|accountant|'
    r'project\s+planner|program\s+manager|operations\s+specialist|lead'
    r')\b',
    re.IGNORECASE,
)


def is_relevant(title: str) -> bool:
    return bool(KEYWORD_RE.search(title)) and not bool(_EXCLUDE_RE.search(title))


# ── Stable ID generation (shared by Workday, iCIMS, Jina) ────────────────────

def make_id(company: str, title: str, url: str) -> str:
    return hashlib.sha256(f"{company}{title}{url}".encode()).hexdigest()[:16]
