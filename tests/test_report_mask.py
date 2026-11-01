"""Masking of ratings and target prices before any reuse (rule 8)."""

from analekh.config import get_settings
from analekh.reports.draft import parse_draft, to_json
from analekh.reports.mask import MASK, mask_draft, mask_text


def test_rating_sentence_is_masked_whole():
    r = mask_text("Margins improved. We upgrade to Buy, TP 1,450. Costs were flat.")
    assert r.text == f"Margins improved. {MASK} Costs were flat."
    assert r.hits == 1


def test_target_price_phrasings_are_masked():
    for s in ("Rs 1,450 target price.", "Our price target is Rs 900.", "Fair value of Rs 800.", "TP: Rs 700", "12-month PT of 1,200"):
        assert mask_text(s).text == MASK, s


def test_recommendation_and_rating_words_are_masked():
    for s in ("The recommendation is unchanged.", "Rating: Outperform.", "We stay Overweight on the stock.", "Reiterate HOLD."):
        assert mask_text(s).text == MASK, s


def test_ordinary_text_is_untouched():
    s = "Net interest margin rose 40 bps. The buyback and selling expenses were stable; holding company debt fell."
    r = mask_text(s)
    assert r.text == s
    assert r.hits == 0


def test_masking_is_idempotent():
    once = mask_text("Target price Rs 500. Costs rose.")
    assert mask_text(once.text).text == once.text


def test_masked_original_never_in_result():
    r = mask_text("We rate it Buy with TP 1,450.")
    assert "1,450" not in repr(r)
    assert "Buy" not in repr(r)


def test_words_and_patterns_come_from_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "rating_words", ["Accumulate-Plus"])
    assert mask_text("We say Accumulate-Plus here.").text == MASK
    assert mask_text("Reiterate Buy.").text == "Reiterate Buy."  # no longer in the list


def test_mask_draft_masks_every_text_field_and_keeps_placeholders():
    draft = parse_draft(
        {
            "schema_version": 1,
            "format": "word",
            "units": [
                {
                    "title": "Summary, target price Rs 10",
                    "blocks": [
                        {"type": "paragraph", "text": "Revenue grew. We recommend Buy."},
                        {"type": "bullets", "items": ["Fine point", "TP Rs 40"]},
                        {"type": "table", "header": ["Line", "Rating"], "rows": [["PAT", "210"], ["View", "Buy"]]},
                        {
                            "type": "chart",
                            "chart_type": "bar",
                            "title": "Price target path",
                            "labels": ["Q1"],
                            "series": [{"name": "PAT", "values": ["1"], "sources": ["fact:1"]}],
                        },
                        {"type": "placeholder", "kind": "rating"},
                    ],
                }
            ],
        }
    )
    out = to_json(mask_draft(draft))
    unit = out["units"][0]
    assert unit["title"] == MASK
    assert unit["blocks"][0]["text"] == f"Revenue grew. {MASK}"
    assert unit["blocks"][1]["items"] == ["Fine point", MASK]
    assert unit["blocks"][2]["header"] == ["Line", MASK]
    assert unit["blocks"][2]["rows"] == [["PAT", "210"], ["View", MASK]]
    assert unit["blocks"][3]["title"] == MASK
    assert unit["blocks"][4] == {"type": "placeholder", "kind": "rating"}
    assert "Buy" not in repr(out)
