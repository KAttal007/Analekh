"""Devices: the label from the User-Agent, the user's own name, the device-cookie key.

Only a fixed vocabulary is ever returned as a label ("Chrome on Windows"): the raw header is
never stored, logged or echoed, so a crafted User-Agent cannot reach the page or the database.
"""

import re
import unicodedata

from analekh.config import get_settings

DEVICE_COOKIE = "analekh_device"
MAX_USER_AGENT = 512  # read no further than this
_KEY = re.compile(r"[A-Za-z0-9_-]{32,64}")  # secrets.token_urlsafe(32) is 43 characters
# letters (with their combining marks, so Devanagari works) and digits in any script, spaces and
# a little punctuation: "Kaushal's laptop (office)". No symbols, controls or format characters.
_NAME_PUNCTUATION = frozenset(" .,'()&+-_")
_NAME_CATEGORIES = ("L", "M", "N")


def _name_char_ok(ch: str) -> bool:
    return ch in _NAME_PUNCTUATION or unicodedata.category(ch)[0] in _NAME_CATEGORIES


def valid_device_key(key: str) -> bool:
    """A cookie value shaped like a key we issued; anything else is ignored, not looked up."""
    return _KEY.fullmatch(key) is not None


class DeviceNameError(ValueError):
    pass


def clean_device_name(raw: str) -> str | None:
    """The user's name for a device, spaces collapsed; empty clears it. Raises DeviceNameError."""
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not name:
        return None
    limit = get_settings().device_name_max_length
    if len(name) > limit:
        raise DeviceNameError(f"Use at most {limit} characters.")
    if not all(_name_char_ok(ch) for ch in name):
        raise DeviceNameError("Use letters, numbers, spaces and . , ' ( ) & + - only.")
    return name


# Order matters: Edge and Opera also say "Chrome/", Chrome also says "Safari/"; iPhone and iPad
# also say "Mac OS X", Android also says "Linux".
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("CrOS", "ChromeOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def device_label(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    ua = user_agent[:MAX_USER_AGENT]
    browser = next((name for key, name in _BROWSERS if key in ua), None)
    system = next((name for key, name in _SYSTEMS if key in ua), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system
