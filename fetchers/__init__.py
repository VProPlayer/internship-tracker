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

EXCLUDE_KEYWORDS = [
    # degree level
    "phd", "ph.d", "doctoral", "doctorate", "postdoc", "post-doc",
    "graduate research", "ms intern", "masters intern", "mba intern",
    "graduate intern", "grad intern", "meng", "m.eng",
    # seniority / non-intern roles
    "senior", "staff", "director", "manager", "head of", "principal",
    "vice president", "account executive", "accountant", "sr.",
    "project planner", "program manager", "operations specialist",
    "specialist", "lead,", ", lead",
]


def is_relevant(title: str) -> bool:
    t = title.lower()
    return bool(KEYWORD_RE.search(t)) and not any(ex in t for ex in EXCLUDE_KEYWORDS)


# ── Stable ID generation (shared by Workday, iCIMS, Jina) ────────────────────

def make_id(company: str, title: str, url: str) -> str:
    return hashlib.sha256(f"{company}{title}{url}".encode()).hexdigest()[:16]
