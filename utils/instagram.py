import re

RESERVED_PATHS = {"p", "reel", "reels", "stories", "explore", "tv", "accounts"}


def parse_instagram_handle(value: str) -> str:
    """Extract @handle from Instagram URL, @handle, or plain username."""
    value = (value or "").strip()
    if not value:
        return ""

    value = value.split("?")[0].rstrip("/")

    for pattern in (
        r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)",
        r"(?:https?://)?instagr\.am/([A-Za-z0-9._]+)",
    ):
        match = re.search(pattern, value, re.I)
        if match:
            handle = match.group(1)
            if handle.lower() not in RESERVED_PATHS:
                return handle.lstrip("@")

    return value.lstrip("@").split("/")[-1].split("?")[0]


def instagram_profile_url(handle: str) -> str:
    handle = parse_instagram_handle(handle)
    return f"https://instagram.com/{handle}" if handle else ""


def normalize_stat(value: str) -> str:
    """Normalize follower/reach text like 1.1m → 1.1M."""
    value = (value or "").strip()
    if not value:
        return "—"
    # Uppercase suffix letter only
    if value[-1].isalpha():
        return value[:-1].strip() + value[-1].upper()
    return value
