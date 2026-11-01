"""Draft one section (or slide) at a time, with its own tool loop and checks.

A section that fails grounding or the style check is returned blocked, never inserted into the
draft silently (rule 3, design doc 17.2). The model writes plain markdown; this module turns it into
draft blocks. Charts and richer blocks come later through the chat.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from analekh.config import get_settings
from analekh.genai.reports import SYSTEM, run_report
from analekh.reports.draft import Block, Bullets, Chart, Heading, Paragraph, Placeholder, Table, Unit

NL = chr(10)

_FORMAT_RULES = (
    "\n5. Write only the body of the section as plain markdown: short paragraphs, '- ' bullets, "
    "and pipe tables where numbers compare. Do not repeat the section title. No em-dashes and no "
    "stock phrases; write as the analyst would."
)


@dataclass
class SectionResult:
    unit: Unit | None  # None when blocked
    blocked: bool
    unmatched: list[str] = field(default_factory=list)
    style: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)  # kept so typed numbers can be checked later
    text: str = ""  # the model's text, for the chat to show a blocked section's numbers
    exchanges: list[dict[str, Any]] = field(default_factory=list)  # for replay in the upgrade check


def style_problems(text: str) -> list[str]:
    """Names the problems (never the text): 'em-dash' and 'phrase:<banned phrase>'."""
    problems: list[str] = []
    if "—" in text:
        problems.append("em-dash")
    for phrase in get_settings().style_banned_phrases:
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            problems.append(f"phrase:{phrase}")
    return problems


def markdown_to_blocks(markdown: str) -> list[Block]:
    blocks: list[Block] = []
    para: list[str] = []
    bullets: list[str] = []
    table: list[str] = []

    def flush() -> None:
        if para:
            blocks.append(Paragraph(type="paragraph", text=" ".join(para)))
            para.clear()
        if bullets:
            blocks.append(Bullets(type="bullets", items=list(bullets)))
            bullets.clear()
        if table:
            rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in table]
            rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            if rows:
                blocks.append(Table(type="table", header=rows[0], rows=rows[1:]))
            table.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif m := re.match(r"^(#{1,3})\s+(.*)$", line):
            flush()
            blocks.append(Heading(type="heading", level=len(m.group(1)), text=m.group(2)))
        elif m := re.match(r"^[-*]\s+(.*)$", line):
            if para or table:
                flush()
            bullets.append(m.group(1))
        elif line.startswith("|"):
            if para or bullets:
                flush()
            table.append(line)
        else:
            if bullets or table:
                flush()
            para.append(line)
    flush()
    return blocks


def draft_section(
    claude: Any,
    executor: Any,
    *,
    company: str,
    report_type: str,
    period_end: str,
    title: str,
    model_id: int | None = None,
    lessons: list[str] | None = None,
    extra: str | None = None,
) -> SectionResult:
    """One section's tool loop. `lessons` are the analyst's active lessons, in plain words."""
    prompt = f"Write the '{title}' part of a {report_type} report for {company}, period ending {period_end}."
    if model_id is not None:
        prompt += f" The analyst's model id is {model_id}; read estimates with get_model_values."
    if lessons:
        prompt += "\n\nThe analyst has taught you these rules; follow them:\n" + "\n".join(f"- {x}" for x in lessons)
    if extra:
        prompt += "\n\n" + extra
    run = run_report(claude, executor, "thread_section", prompt=prompt, system_text=SYSTEM + _FORMAT_RULES)
    problems = style_problems(run.text)
    blocked = run.blocked or bool(problems)
    unit = None if blocked else Unit(title=title, blocks=markdown_to_blocks(run.text))
    return SectionResult(unit, blocked, list(run.grounding.unmatched), problems, run.tool_calls, run.results, run.text, run.exchanges)


def unit_to_markdown(unit: Unit) -> str:
    """A unit as the model reads it. Charts and placeholders appear as one-line notes."""
    out: list[str] = []
    for b in unit.blocks:
        if isinstance(b, Heading):
            out.append(f"{'#' * (b.level + 1)} {b.text}")
        elif isinstance(b, Paragraph):
            out.append(b.text)
        elif isinstance(b, Bullets):
            out.append(NL.join(f"- {i}" for i in b.items))
        elif isinstance(b, Table):
            out.append(NL.join(["| " + " | ".join(b.header) + " |", "|" + "---|" * len(b.header), *("| " + " | ".join(r) + " |" for r in b.rows)]))
        elif isinstance(b, Chart):
            out.append(f"[chart: {b.title}; series: {', '.join(s.name for s in b.series)}; labels: {', '.join(b.labels)}]")
        elif isinstance(b, Placeholder):
            out.append(f"[left for the analyst: {b.kind}]")
    separator = NL + NL
    return separator.join(out)
