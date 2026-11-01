"""Mask ratings, target prices and guidance before any reuse (rule 8).

Text that leaves a thread for an export, a prompt example or the lesson job passes through here.
Two layers: placeholder blocks never hold a value (draft.py), and every sentence that looks like a
rating or a target price is replaced by a mask. Whole sentences go, so "We upgrade to Buy, TP 1,450"
leaves nothing behind. When in doubt it masks. Guidance lives only in its placeholder: management's
guidance in ordinary text is content, not the analyst's view.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from analekh.config import get_settings
from analekh.reports.draft import Block, Bullets, Chart, ChartSeries, Draft, Heading, Paragraph, Table, Unit

MASK = "[masked]"
_SENTENCE_GAP = re.compile(r"(?<=[.!?])(\s+)")


@dataclass(frozen=True)
class MaskResult:
    """The masked text and how many sentences were masked. It never holds the original."""

    text: str
    hits: int


@lru_cache(maxsize=8)
def _compiled(words: tuple[str, ...], patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    found = [rf"\b{re.escape(w)}\b" for w in words if w.strip()]
    return tuple(re.compile(p, re.IGNORECASE) for p in [*found, *patterns])


def _matchers() -> tuple[re.Pattern[str], ...]:
    cfg = get_settings()
    return _compiled(tuple(cfg.rating_words), tuple(cfg.target_patterns))


def mask_text(text: str) -> MaskResult:
    matchers = _matchers()
    parts = _SENTENCE_GAP.split(text)  # sentences at even positions, their whitespace between
    hits = 0
    for i in range(0, len(parts), 2):
        if any(m.search(parts[i]) for m in matchers):
            parts[i] = MASK
            hits += 1
    return MaskResult("".join(parts), hits)


def _m(text: str) -> str:
    return mask_text(text).text


def mask_draft(draft: Draft) -> Draft:
    """A copy of the draft with every text field masked. Placeholders carry no value and stay as they are."""
    units: list[Unit] = []
    for unit in draft.units:
        blocks: list[Block] = []
        for b in unit.blocks:
            if isinstance(b, Heading | Paragraph):
                blocks.append(b.model_copy(update={"text": _m(b.text)}))
            elif isinstance(b, Bullets):
                blocks.append(b.model_copy(update={"items": [_m(i) for i in b.items]}))
            elif isinstance(b, Table):
                blocks.append(b.model_copy(update={"header": [_m(h) for h in b.header], "rows": [[_m(c) for c in r] for r in b.rows]}))
            elif isinstance(b, Chart):
                series = [ChartSeries(name=_m(s.name), values=s.values, sources=s.sources) for s in b.series]
                blocks.append(b.model_copy(update={"title": _m(b.title), "labels": [_m(x) for x in b.labels], "series": series}))
            else:
                blocks.append(b)
        units.append(Unit(title=_m(unit.title), blocks=blocks))
    return Draft(schema_version=draft.schema_version, format=draft.format, units=units)
