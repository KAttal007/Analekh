"""The fixed outline of each report: what the first draft contains, in order.

Mirrors the lists shown on the Reports screen (web/src/pages/Reports.tsx). The server owns them
here so a draft is generated section by section, and one section can be redone.
"""

_OUTLINES: dict[tuple[str, str], list[str]] = {
    ("quarterly", "word"): ["Results highlights", "Concall highlights", "Risks and future guidance", "Investment rationale"],
    ("quarterly", "ppt"): ["Results at a glance", "Segment and KPI update", "Concall takeaways", "Outlook and risks"],
    (
        "initiating",
        "word",
    ): [
        "Investment summary",
        "MD&A and business",
        "Financial performance",
        "Sector performance",
        "Company outlook",
        "Strengths and risks",
        "Investment rationale",
    ],
    ("initiating", "ppt"): ["Investment summary", "Business model", "Financials", "Valuation context", "Risks"],
}


def outline(report_type: str, fmt: str) -> list[str]:
    try:
        return list(_OUTLINES[(report_type, fmt)])
    except KeyError:
        raise ValueError("no outline for this report type and format") from None
