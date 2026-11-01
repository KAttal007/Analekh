"""Model-neutral draft document (design: the draft document)."""

import pytest

from analekh.config import get_settings
from analekh.reports.draft import DraftError, parse_draft, to_json


def _word_draft() -> dict:
    return {
        "schema_version": 1,
        "format": "word",
        "units": [
            {
                "title": "Results highlights",
                "blocks": [
                    {"type": "heading", "level": 2, "text": "Quarter at a glance"},
                    {"type": "paragraph", "text": "Net profit rose 12% [fact:123 filing:9 context:OneD]."},
                    {"type": "bullets", "items": ["NIM held at 3.1% [kpi:44]", "Costs flat [calc]"]},
                    {"type": "table", "header": ["Line", "Q2"], "rows": [["Revenue", "1,200"], ["PAT", "210"]]},
                    {
                        "type": "chart",
                        "chart_type": "bar",
                        "title": "Net profit",
                        "labels": ["Q1", "Q2"],
                        "series": [{"name": "PAT", "values": ["190.5", "210"], "sources": ["fact:123"]}],
                    },
                    {"type": "placeholder", "kind": "rating"},
                    {"type": "placeholder", "kind": "target"},
                    {"type": "placeholder", "kind": "guidance"},
                ],
            }
        ],
    }


def test_every_block_type_round_trips():
    draft = parse_draft(_word_draft())
    assert to_json(draft) == _word_draft()


def test_unknown_block_type_is_refused():
    obj = _word_draft()
    obj["units"][0]["blocks"].append({"type": "script", "text": "x"})
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_placeholder_cannot_carry_a_value():
    obj = _word_draft()
    obj["units"][0]["blocks"][5]["value"] = "Buy"
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_chart_series_without_a_source_is_refused():
    obj = _word_draft()
    obj["units"][0]["blocks"][4]["series"][0]["sources"] = []
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_chart_values_must_be_decimal_strings_not_floats():
    obj = _word_draft()
    obj["units"][0]["blocks"][4]["series"][0]["values"] = [190.5, 210]
    with pytest.raises(DraftError):
        parse_draft(obj)
    obj["units"][0]["blocks"][4]["series"][0]["values"] = ["abc", "210"]
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_unknown_field_is_refused():
    obj = _word_draft()
    obj["units"][0]["extra"] = 1
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_wrong_format_or_schema_version_is_refused():
    for change in ({"format": "pdf"}, {"schema_version": 2}):
        with pytest.raises(DraftError):
            parse_draft({**_word_draft(), **change})


def test_too_many_units_is_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "draft_max_units", 1)
    obj = _word_draft()
    obj["units"].append({"title": "Risks", "blocks": []})
    with pytest.raises(DraftError):
        parse_draft(obj)


def test_too_many_blocks_is_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "draft_max_blocks", 3)
    with pytest.raises(DraftError):
        parse_draft(_word_draft())


def test_overlong_text_is_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "draft_max_text_chars", 10)
    with pytest.raises(DraftError):
        parse_draft(_word_draft())


def test_not_a_dict_is_refused():
    with pytest.raises(DraftError):
        parse_draft(["units"])  # type: ignore[arg-type]


def test_chart_series_needs_one_value_per_label():
    obj = _word_draft()
    obj["units"][0]["blocks"][4]["series"][0]["values"] = ["1"]
    with pytest.raises(DraftError):
        parse_draft(obj)
