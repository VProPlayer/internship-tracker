import re

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

_US_TERMS = ("united states", "usa", "u.s.a", "u.s.", "remote", "hybrid")

# Matches ", CA" / ", NY" etc. at end of location string or before a zip
_STATE_RE = re.compile(r',\s*([A-Z]{2})(?:\s+\d{5})?(?:\s*$|,)', re.IGNORECASE)


def is_us_location(location: str) -> bool:
    """Return True if location is US-based, remote, or unknown."""
    if not location:
        return True  # no location data — don't exclude

    loc = location.strip().lower()

    if any(term in loc for term in _US_TERMS):
        return True

    # Check for state abbreviation pattern: "City, CA" or "City, CA 12345"
    m = _STATE_RE.search(location)
    if m and m.group(1).upper() in _US_STATES:
        return True

    return False
