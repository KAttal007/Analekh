"""Section drafting with grounding and style checks (design: the first draft)."""

from types import SimpleNamespace

import pytest

from analekh.genai.tools import ToolExecutor
from analekh.reports.draft import Bullets, Heading, Paragraph, Table
from analekh.reports.outlines import outline
from analekh.reports.sections import draft_section, markdown_to_blocks, style_problems


class FakeClaude:
    """First asks for a calc (1/8 = 12.5), then writes `final_text`."""

    model = "fake"

    def __init__(self, final_text: str):
        self.final_text = final_text
        self.turn = 0
        self.prompts: list[str] = []

    def create(self, purpose, **kwargs):
        self.turn += 1
        self.prompts.append(str(kwargs.get("messages")))
        if self.turn == 1:
            block = SimpleNamespace(
                type="tool_use",
                id="t1",
                name="calc",
                input={"expression": "a/b*100", "inputs": [{"name": "a", "value": 1}, {"name": "b", "value": 8}]},
            )
            msg = SimpleNamespace(stop_reason="tool_use", content=[block])
            return SimpleNamespace(text="", message=msg, input_tokens=10, output_tokens=5)
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.final_text)])
        return SimpleNamespace(text=self.final_text, message=msg, input_tokens=10, output_tokens=5)


def _draft(final_text: str, **kw):
    claude = FakeClaude(final_text)
    res = draft_section(
        claude,
        ToolExecutor(session=None),
        company="DEMO",
        report_type="quarterly",
        period_end="2026-09-30",
        title="Results highlights",
        **kw,
    )
    return res, claude


def test_grounded_section_becomes_a_unit():
    res, _ = _draft("Margin was 12.5% [calc].\n\n- Costs were flat.")
    assert not res.blocked
    assert res.unit is not None and res.unit.title == "Results highlights"
    assert isinstance(res.unit.blocks[0], Paragraph)
    assert isinstance(res.unit.blocks[1], Bullets)
    assert res.results, "tool results are kept so typed numbers can be checked later"
    assert res.tool_calls[0]["tool"] == "calc"


def test_ungrounded_number_blocks_the_section():
    res, _ = _draft("Margin was 14.0%.")
    assert res.blocked and res.unit is None
    assert res.unmatched == ["14.0%"]


def test_em_dash_blocks_the_section():
    res, _ = _draft("Margin was 12.5% — a steady quarter [calc].")
    assert res.blocked and res.unit is None
    assert "em-dash" in res.style


def test_lessons_reach_the_prompt():
    _, claude = _draft("Margin was 12.5% [calc].", lessons=["Lead with NIM, not PAT"])
    assert "Lead with NIM, not PAT" in claude.prompts[0]


def test_style_problems_names_the_problem_without_echoing_text():
    assert style_problems("Fine text.") == []
    assert style_problems("A — B") == ["em-dash"]
    assert style_problems("Let us DELVE into it.") == ["phrase:delve"]


def test_markdown_to_blocks_covers_headings_bullets_tables_and_paragraphs():
    blocks = markdown_to_blocks("## Segments\nFirst line\ncontinues here.\n\n- one\n- two\n\n| Line | Q2 |\n|---|---|\n| Rev | 10 |\n")
    assert [type(b) for b in blocks] == [Heading, Paragraph, Bullets, Table]
    assert blocks[0].level == 2
    assert blocks[1].text == "First line continues here."
    assert blocks[2].items == ["one", "two"]
    assert blocks[3].header == ["Line", "Q2"] and blocks[3].rows == [["Rev", "10"]]


def test_outlines_follow_the_reports_screen():
    assert outline("quarterly", "word") == ["Results highlights", "Concall highlights", "Risks and future guidance", "Investment rationale"]
    assert len(outline("initiating", "word")) == 7
    assert len(outline("quarterly", "ppt")) == 4
    assert len(outline("initiating", "ppt")) == 5
    with pytest.raises(ValueError):
        outline("ipo", "word")
