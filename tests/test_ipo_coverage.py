"""IPO tools and the coverage generator (plan Task 7). Scripted Claude; no network."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from analekh.db.models import IpoDocument, IpoFinancial, IpoIssue
from analekh.ipo.coverage import (
    RATING_PLACEHOLDER,
    RATIONALE_PLACEHOLDER,
    SECTIONS,
    generate,
)
from analekh.ipo.tools import IPO_TOOL_DEFS, IpoToolExecutor


class SectionClaude:
    """Answers each section's prompt with fixed text; no tool calls, so only numbers in the text
    itself are checked (none of them are grounded)."""

    model = "fake"

    def __init__(self, texts: dict[str, str]):
        self.texts = texts
        self.tool_sets: list[list[str]] = []

    def create(self, purpose, **kwargs):
        self.tool_sets.append([t["name"] for t in kwargs.get("tools", [])])
        key = purpose.removeprefix("report:ipo_")  # run_report purpose is "report:<kind>"
        text = self.texts.get(key, "The section is clean.")
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])
        return SimpleNamespace(text=text, message=msg, input_tokens=1, output_tokens=1)


def _issue(db, stem="coverage co"):
    issue = IpoIssue(stem=stem, name="Coverage Co Limited")
    db.add(issue)
    db.flush()
    return issue


def _doc(db, issue, stage, sha, status="extracted", sebi="1"):
    doc = IpoDocument(
        issue_id=issue.id,
        stage=stage,
        sebi_id=sebi,
        entry_url="e",
        pdf_url="p",
        file_sha256=sha,
        storage_key=f"{sha}.pdf",
        status=status,
        meta={"terms": {"page": 3, "price_band_low": "700", "price_band_high": "750"}},
    )
    db.add(doc)
    db.flush()
    return doc


def _figure(db, doc, amount, line="revenue_from_operations"):
    db.add(
        IpoFinancial(
            document_id=doc.id,
            basis="consolidated",
            period_end=date(2026, 3, 31),
            period_label="FY26",
            is_stub=False,
            line=line,
            amount=Decimal(amount),
            unit="INR",
            page=120,
        )
    )
    db.flush()


def test_generate_needs_a_document(db):
    issue = _issue(db, "nodoc")
    with pytest.raises(ValueError, match="no offer document yet"):
        generate(db, SectionClaude({}), issue.id, "analyst@example.com")


def test_generate_works_from_rhp_alone(db):
    issue = _issue(db, "rhp only")
    _doc(db, issue, "rhp", "r" * 64)
    draft = generate(db, SectionClaude({}), issue.id, "analyst")
    assert draft.sections["stage"] == "rhp"


def test_each_section_grounded_separately(db):
    issue = _issue(db, "grounded")
    _doc(db, issue, "rhp", "g" * 64)
    claude = SectionClaude({"valuation": "Multiple of 999 times earnings."})
    draft = generate(db, claude, issue.id, "analyst")
    assert draft.sections["valuation"]["blocked"] is True
    assert draft.sections["valuation"]["unmatched"] == ["999"]
    assert draft.sections["mdna"]["blocked"] is False


def test_blocked_section_is_never_clean(db):
    issue = _issue(db, "blocked")
    _doc(db, issue, "rhp", "h" * 64)
    claude = SectionClaude({"mdna": "Revenue of 4321 crore."})
    draft = generate(db, claude, issue.id, "analyst")
    section = draft.sections["mdna"]
    assert section["blocked"] is True
    assert "4321" in section["text"]


def test_placeholders_present_and_no_value_stored(db):
    issue = _issue(db, "placeholders")
    _doc(db, issue, "rhp", "p" * 64)
    draft = generate(db, SectionClaude({}), issue.id, "analyst")
    assert draft.sections["rating"] == RATING_PLACEHOLDER
    assert draft.sections["rationale"] == RATIONALE_PLACEHOLDER
    assert not any("target" in str(draft.sections[k]).lower() for k in SECTIONS)


def test_dash_is_flagged(db):
    issue = _issue(db, "dash")
    _doc(db, issue, "rhp", "d" * 64)
    claude = SectionClaude({"strengths_and_risks": "Strong brand — wide reach."})
    draft = generate(db, claude, issue.id, "analyst")
    assert draft.sections["strengths_and_risks"]["style_issues"]


def test_tool_reads_only_current_document(db):
    issue = _issue(db, "current")
    rhp = _doc(db, issue, "rhp", "e" * 64)
    pro = _doc(db, issue, "prospectus", "f" * 64, sebi="2")
    _figure(db, rhp, "1000")
    _figure(db, pro, "1100")
    rows = IpoToolExecutor(db, issue.id).run("get_ipo_financials", {"basis": "consolidated", "lines": ["revenue_from_operations"]})
    assert len(rows) == 1
    assert Decimal(rows[0]["amount"]) == Decimal("1100")
    assert rows[0]["source"].startswith(f"ipo_doc:{pro.id} ")


def test_offer_terms_tool_names_its_source(db):
    issue = _issue(db, "terms tool")
    doc = _doc(db, issue, "rhp", "t" * 64)
    terms = IpoToolExecutor(db, issue.id).run("get_offer_terms", {})
    assert terms["price_band_low"] == "700"
    assert terms["source"] == f"ipo_doc:{doc.id} page:3"


def test_coverage_uses_ipo_tools_only(db):
    issue = _issue(db, "toolset")
    _doc(db, issue, "rhp", "k" * 64)
    claude = SectionClaude({})
    generate(db, claude, issue.id, "analyst")
    names = {n for names in claude.tool_sets for n in names}
    assert names <= {t["name"] for t in IPO_TOOL_DEFS}
    assert "get_ipo_financials" in names
