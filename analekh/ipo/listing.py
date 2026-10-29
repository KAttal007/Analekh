"""SEBI offer-document lists and entry pages. Pure parsing: no network here.

Layout, from the live fetch of Jio Platforms Limited on 29 October 2026 (captures are in the
gitignored out/sebi-captures/ folder):

- A list row is `<tr><td>Mon D, YYYY</td><td><a href=ENTRY_URL title=...>TITLE</a></td></tr>`,
  newest first.
- An RHP row also nests an abridged-prospectus link under /sebi_data/commondocs/ inside the
  title. That path is not on the allow-list and is not used: only the first anchor is read.
- Titles differ between stages: "Jio Platforms Limited – RHP" (en dash, 15 Oct, entry 105274) and
  "Jio Platforms Ltd.- Prospectus" (26 Oct, entry 105427). A Prospectus is a new entry, not a
  replacement of the RHP.
- The entry page embeds the PDF in an iframe whose `file=` parameter holds the real URL under
  /sebi_data/attachdocs/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

from lxml import html as lxml_html

from analekh.ingest.http import ALLOWED_HOSTS, path_allowed

BASE = "https://www.sebi.gov.in/"
ENTRY_PATH = "/filings/public-issues/"
ATTACH_PATH = "/sebi_data/attachdocs/"

_STAGE_PHRASES = ("red herring", "draft")
_STAGE_WORDS = {"rhp", "prospectus"}
_FORM_WORDS = {"ltd", "limited", "pvt", "private", "inc"}
_SEBI_ID = re.compile(r"_(\d+)\.html?$")
_FILE_PARAM = re.compile(r"[?&]file=([^'\"&\s>]+)")


@dataclass
class ListEntry:
    sebi_id: str
    title: str
    entry_url: str
    filed_on: date | None
    stage: str


def _on_entry_path(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS and path_allowed(parts.hostname, parts.path) and parts.path.startswith(ENTRY_PATH)


def parse_list(html: str, stage: str) -> list[ListEntry]:
    """Rows in page order (newest first). Rows whose entry link is not an allowed entry page are
    dropped, not guessed at."""
    doc = lxml_html.fromstring(html)
    entries: list[ListEntry] = []
    for row in doc.xpath("//tr[@role='row'][td]"):
        cells = row.xpath("./td")
        if len(cells) < 2:
            continue
        anchors = cells[1].xpath(".//a[@href]")
        if not anchors:
            continue
        first = anchors[0]
        entry_url = urljoin(BASE, first.get("href", "").strip())
        if not _on_entry_path(entry_url):
            continue
        match = _SEBI_ID.search(urlsplit(entry_url).path)
        if match is None:
            continue
        date_text = " ".join(cells[0].text_content().split())
        try:
            filed_on: date | None = datetime.strptime(date_text, "%b %d, %Y").date()
        except ValueError:
            filed_on = None
        title = " ".join(first.text_content().split())
        entries.append(
            ListEntry(
                sebi_id=match.group(1),
                title=title,
                entry_url=entry_url,
                filed_on=filed_on,
                stage=stage,
            )
        )
    return entries


def pdf_url(entry_html: str, entry_url: str) -> str:
    """The offer PDF embedded on an entry page. Raises ValueError when there is none, or when the
    URL it names is off the allow-list (host or path)."""
    for match in _FILE_PARAM.finditer(entry_html):
        candidate = urljoin(entry_url, match.group(1))
        parts = urlsplit(candidate)
        if parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS and path_allowed(parts.hostname, parts.path) and parts.path.startswith(ATTACH_PATH) and parts.path.lower().endswith(".pdf"):
            return candidate
    raise ValueError("no offer PDF on the entry page")


def issue_stem(title: str) -> str:
    """Company name shared by the RHP and the Prospectus of one issue."""
    text = title.lower().replace("–", " ").replace("—", " ")
    for phrase in _STAGE_PHRASES:
        text = text.replace(phrase, " ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    words = [w for w in text.split() if w not in _STAGE_WORDS | _FORM_WORDS]
    return " ".join(words)
