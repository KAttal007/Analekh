"""Offer terms (price band, issue size, shares) and the listed peers used for valuation.

Every number comes back as a string, converted with to_rupees (Decimal-safe). A figure the
document does not print is None, never zero.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from analekh.docs.pdf import PageText, read_pages, subset
from analekh.genai.client import Claude
from analekh.ipo.statements import to_rupees

MAX_TERMS_PAGES = 20
_TERMS_RE = re.compile(
    r"price band|basis for offer price|comparison with listed industry peers|objects of the offer",
    re.IGNORECASE,
)

_NUM = {"type": ["string", "null"]}
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "page",
        "price_band_low",
        "price_band_high",
        "face_value",
        "fresh_issue_amount",
        "offer_for_sale_amount",
        "amount_unit",
        "post_issue_shares",
        "peers",
    ],
    "properties": {
        "page": {"type": "integer"},
        "price_band_low": _NUM,
        "price_band_high": _NUM,
        "face_value": _NUM,
        "fresh_issue_amount": _NUM,
        "offer_for_sale_amount": _NUM,
        "amount_unit": {"type": "string"},
        "post_issue_shares": _NUM,
        "peers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "pe", "eps", "ronw", "page"],
                "properties": {
                    "name": {"type": "string"},
                    "pe": _NUM,
                    "eps": _NUM,
                    "ronw": _NUM,
                    "page": {"type": "integer"},
                },
            },
        },
    },
}

_PROMPT = (
    "The pages below come from an Indian offer document. Return the price band (low and high, rupees "
    "per share), face value, fresh issue and offer for sale amounts (in the unit given in amount_unit), "
    "post-issue shares, and the listed peers from the comparison table with their P/E, EPS and RoNW. "
    "Numbers are strings exactly as printed. Use null for anything not printed. Do not compute.\n\n"
)


def select_terms_pages(pages: list[PageText]) -> list[int]:
    matches = [p.number for p in pages if _TERMS_RE.search(p.text)]
    return sorted(matches)[:MAX_TERMS_PAGES]


def _rupees(raw: str | None, unit: str) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return format(to_rupees(str(raw), unit), "f")
    except ValueError:
        return None


def _plain(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip().replace(",", "")
    try:
        Decimal(text)
    except InvalidOperation:
        return None
    return text


def extract_terms(claude: Claude, pdf: bytes, page_numbers: list[int]) -> dict[str, Any]:
    if not page_numbers:
        return {"peers": [], "page": None}
    pages = read_pages(subset(pdf, page_numbers))
    body = "\n".join(f"=== PDF page {page_numbers[p.number - 1]} ===\n{p.text}" for p in pages)
    answer = claude.create_json(
        "ipo_terms",
        _SCHEMA,
        messages=[{"role": "user", "content": _PROMPT + body}],
    )
    unit = answer.get("amount_unit") or "INR"
    peers = []
    for peer in answer.get("peers", []):
        if int(peer.get("page", 0)) not in page_numbers:
            continue
        peers.append(
            {
                "name": str(peer["name"]),
                "pe": _plain(peer.get("pe")),
                "eps": _plain(peer.get("eps")),
                "ronw": _plain(peer.get("ronw")),
                "page": int(peer["page"]),
            }
        )
    return {
        "page": answer.get("page"),
        "price_band_low": _plain(answer.get("price_band_low")),
        "price_band_high": _plain(answer.get("price_band_high")),
        "face_value": _plain(answer.get("face_value")),
        "fresh_issue_amount": _rupees(answer.get("fresh_issue_amount"), unit),
        "offer_for_sale_amount": _rupees(answer.get("offer_for_sale_amount"), unit),
        "post_issue_shares": _rupees(answer.get("post_issue_shares"), "INR"),
        "peers": peers,
    }
