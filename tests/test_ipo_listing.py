"""SEBI offer-document list and entry-page parsing (plan Task 2). Synthetic HTML shaped like the
live captures of 29 October 2026 (Jio Platforms Limited RHP and Prospectus)."""

from datetime import date

import pytest

from analekh.ipo.listing import issue_stem, parse_list, pdf_url

LIST_HTML = """
<table id='sample_1' role='grid'><thead><tr role='row'><th>Date</th><th>Title</th></tr></thead>
<tbody>
<tr role='row' class='odd'>
  <td>Oct 26, 2026</td>
  <td><a href="https://www.sebi.gov.in/filings/public-issues/oct-2026/jio-platforms-ltd-prospectus_105427.html"
     target="_blank" title="Jio Platforms Ltd.- Prospectus" class="points"> Jio Platforms Ltd.- Prospectus</a></td>
</tr>
<tr role='row' class='odd'>
  <td>Oct 15, 2026</td>
  <td><a href="https://www.sebi.gov.in/filings/public-issues/oct-2026/jio-platforms-limited-rhp_105274.html"
     target="_blank" title="Jio Platforms Limited – RHP <br><a href='https://www.sebi.gov.in/sebi_data/commondocs/oct-2026/Jio%20Platforms%20Limited_p.pdf'>Abridged</a>"
     class="points"> Jio Platforms Limited – RHP <br><a href='https://www.sebi.gov.in/sebi_data/commondocs/oct-2026/Jio%20Platforms%20Limited_p.pdf'
     style=color:#000000>Jio Platforms Limited -  Abridged Prospectus</a></a></td>
</tr>
</tbody></table>
"""

ENTRY_HTML = """
<html><body><div>
<iframe src='../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1793005577827.pdf'
  width='100%' title="Jio Platforms Ltd.- Prospectus">Jio Platforms Ltd.- Prospectus</iframe>
</div></body></html>
"""


def test_parse_list_returns_entries_in_order():
    entries = parse_list(LIST_HTML, "prospectus")
    assert [e.sebi_id for e in entries] == ["105427", "105274"]
    assert entries[0].entry_url == ("https://www.sebi.gov.in/filings/public-issues/oct-2026/jio-platforms-ltd-prospectus_105427.html")
    assert entries[0].filed_on == date(2026, 10, 26)
    assert entries[1].filed_on == date(2026, 10, 15)
    assert entries[0].stage == "prospectus"


def test_parse_list_ignores_nested_abridged_link():
    entries = parse_list(LIST_HTML, "rhp")
    rhp = entries[1]
    assert rhp.entry_url.endswith("jio-platforms-limited-rhp_105274.html")
    assert "commondocs" not in rhp.entry_url
    assert "<" not in rhp.title


def test_parse_list_drops_links_off_the_public_issues_path():
    hostile = LIST_HTML.replace(
        "https://www.sebi.gov.in/filings/public-issues/oct-2026/jio-platforms-ltd-prospectus_105427.html",
        "https://evil.example/filings/public-issues/x_1.html",
    )
    assert [e.sebi_id for e in parse_list(hostile, "prospectus")] == ["105274"]


def test_pdf_url_from_entry_page():
    url = pdf_url(ENTRY_HTML, "https://www.sebi.gov.in/filings/public-issues/oct-2026/x_105427.html")
    assert url == "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1793005577827.pdf"


def test_pdf_url_missing_raises():
    with pytest.raises(ValueError):
        pdf_url("<html></html>", "https://www.sebi.gov.in/filings/public-issues/x_1.html")


def test_pdf_url_off_allow_list_raises():
    bad = ENTRY_HTML.replace(
        "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1793005577827.pdf",
        "https://evil.example/sebi_data/attachdocs/x.pdf",
    )
    with pytest.raises(ValueError):
        pdf_url(bad, "https://www.sebi.gov.in/filings/public-issues/x_1.html")


def test_issue_stem_joins_ltd_and_limited():
    assert issue_stem("Jio Platforms Limited – RHP") == "jio platforms"
    assert issue_stem("Jio Platforms Ltd.- Prospectus") == "jio platforms"
    assert issue_stem("Jio Platforms Limited - Prospectus") == "jio platforms"


def test_issue_stem_keeps_different_companies_apart():
    assert issue_stem("Jio Platforms Limited – RHP") != issue_stem("Jio Financial Services Limited – RHP")
    assert issue_stem("Jio Financial Services Ltd.- Prospectus") == "jio financial services"


def test_issue_stem_drops_red_herring_phrase():
    assert issue_stem("Zetwerk Manufacturing Businesses Limited - Red Herring Prospectus") == ("zetwerk manufacturing businesses")
