import re

US_STATE_NAMES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia",
]
US_STATE_ABBR = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia",
    "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt",
    "va", "wa", "wv", "wi", "wy", "dc",
]
# Places outside the US whose names contain a US state name, which would otherwise read as US
NON_US_LOOKALIKES = ["baja california"]
_STATE_NAME_RE = re.compile(r"\b(" + "|".join(US_STATE_NAMES) + r")\b", re.IGNORECASE)
_STATE_ABBR_RE = re.compile(r",\s*(" + "|".join(US_STATE_ABBR) + r")\b", re.IGNORECASE)
_WORKPLACE_TYPES = {"in-office", "remote", "hybrid", "on-site", "onsite", "flexible"}


def text_indicates_us(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if stripped.upper() in ("US", "USA"):
        return True
    lowered = stripped.lower()
    if "united states" in lowered:
        return True
    for lookalike in NON_US_LOOKALIKES:
        lowered = lowered.replace(lookalike, "")
    if _STATE_NAME_RE.search(lowered):
        return True
    if _STATE_ABBR_RE.search(lowered):
        return True
    return False


def text_country_hint(text: str) -> str | None:
    """Best-effort non-US country name from a 'City, Country' shaped string. Returns None
    if the string doesn't look informative (workplace type, bare city with no qualifier)."""
    if not text:
        return None
    stripped = text.strip()
    if stripped.lower() in _WORKPLACE_TYPES or "," not in stripped:
        return None
    last = stripped.split(",")[-1].strip()
    if not last or last.lower() in _WORKPLACE_TYPES or len(last) <= 3:
        return None
    return last


def detect_country(candidates: list[str]) -> str | None:
    """Given a list of location-ish strings for a job, return 'US', a non-US country
    name, or None if genuinely ambiguous (e.g. a bare city name with no other signal)."""
    candidates = [c for c in candidates if c]

    if any(text_indicates_us(text) for text in candidates):
        return "US"

    for text in candidates:
        hint = text_country_hint(text)
        if hint:
            return hint

    return None
