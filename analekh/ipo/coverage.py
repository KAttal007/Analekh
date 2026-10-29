"""IPO coverage draft: one grounded report run per section, against the IPO tools.

Sections are drafted from the current offer document (the Prospectus if filed, else the RHP).
The rating and the rationale are placeholders for the analyst: the AI never fills them, and no
target price appears anywhere (owner, 29 October; rule 8).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from analekh.db.models import IpoDraft
from analekh.genai.client import Claude
from analekh.genai.reports import SYSTEM, run_report
from analekh.ipo.tools import IPO_TOOL_DEFS, IpoToolExecutor
from analekh.ipo.versions import current_document

SECTIONS = ("mdna", "financial_performance", "sector_performance", "strengths_and_risks", "valuation")
RATING_PLACEHOLDER = "[Analyst to set rating]"
RATIONALE_PLACEHOLDER = "[Analyst rationale]"

_RULES = (
    " Use only the tools provided: get_ipo_financials, get_offer_terms, search_offer_text and calc. "
    "State only numbers those tools return, or numbers calc computes; cite the source field after each "
    "figure. Do not state a rating, a recommendation or a target price. Do not use em-dashes or en-dashes. "
    "If the document does not show something, say so."
)

SECTION_PROMPTS: dict[str, str] = {
    "mdna": (
        "Write the management discussion and analysis summary for the company in this offer document: "
        "what the three restated years and the stub period show, and what management says drives them "
        "(search_offer_text)." + _RULES
    ),
    "financial_performance": (
        "Write the financial performance section: revenue, profit after tax, EPS and borrowings across "
        "the restated years, both consolidated and standalone, with year on year changes computed with "
        "calc." + _RULES
    ),
    "sector_performance": ("Write the sector performance section from the industry chapter of this offer document: market size, growth and the company's position, using search_offer_text." + _RULES),
    "strengths_and_risks": (
        "Write the strengths and risks section from the business description and risk factors of this offer document, using search_offer_text. Keep each point tied to the document." + _RULES
    ),
    "valuation": (
        "Write the valuation context section. Using the price band and the listed peers from "
        "get_offer_terms, compute the implied price to earnings and price to book at the price band "
        "with calc, and set them against the peers' figures. Never state a target price or a rating." + _RULES
    ),
}


class NoOfferDocument(ValueError):
    """The issue has no read RHP or Prospectus yet. The only error the API reports as a 409."""


@dataclass
class SectionResult:
    key: str
    text: str
    blocked: bool
    unmatched: list[str]
    style_issues: list[str]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _style_issues(text: str) -> list[str]:
    issues: list[str] = []
    if "—" in text:
        issues.append("em-dash")
    if "–" in text:
        issues.append("en-dash")
    return issues


def generate(session: Session, claude: Claude, issue_id: int, user: str) -> IpoDraft:
    doc = current_document(session, issue_id)
    if doc is None or doc.status not in ("extracted", "flagged"):
        raise NoOfferDocument("no offer document yet")
    executor = IpoToolExecutor(session, issue_id)
    sections: dict[str, Any] = {}
    for key in SECTIONS:
        try:
            run = run_report(
                claude,
                executor,
                f"ipo_{key}",
                tools=IPO_TOOL_DEFS,
                system_text=SYSTEM,
                prompt=SECTION_PROMPTS[key],
            )
            result = SectionResult(
                key=key,
                text=run.text,
                blocked=run.blocked,
                unmatched=list(run.grounding.unmatched),
                style_issues=_style_issues(run.text),
                tool_calls=run.tool_calls,
            )
        except RuntimeError:
            # The section did not finish within its turns: blocked, never shown as clean.
            result = SectionResult(key, "", True, ["section did not finish"], [], [])
        sections[key] = asdict(result)
    sections["rating"] = RATING_PLACEHOLDER
    sections["rationale"] = RATIONALE_PLACEHOLDER
    sections["stage"] = doc.stage
    draft = IpoDraft(issue_id=issue_id, document_id=doc.id, sections=sections, created_by=user)
    session.add(draft)
    session.flush()
    return draft
