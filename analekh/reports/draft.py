"""The draft document: one closed JSON structure that no model owns.

A Word report is a list of sections and a PowerPoint a list of slides; both are `Unit`s holding
blocks. Citations stay inside text as markers such as `[fact:123]`. A chart is a spec whose series
point at their sources, never an image. Rating, target price and guidance are `Placeholder`
blocks that can never carry a value (rule 8). Amounts in charts are decimal strings, never floats
(rule 4).
"""

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from analekh.config import get_settings

SCHEMA_VERSION = 1


class DraftError(ValueError):
    """The draft is not valid. The message names where, never what: draft text stays out of errors."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Heading(_Closed):
    type: Literal["heading"]
    level: Annotated[StrictInt, Field(ge=1, le=3)]
    text: StrictStr


class Paragraph(_Closed):
    type: Literal["paragraph"]
    text: StrictStr


class Bullets(_Closed):
    type: Literal["bullets"]
    items: list[StrictStr]


class Table(_Closed):
    type: Literal["table"]
    header: list[StrictStr]
    rows: list[list[StrictStr]]


class ChartSeries(_Closed):
    name: StrictStr
    values: list[StrictStr]
    sources: Annotated[list[StrictStr], Field(min_length=1)]

    @field_validator("values")
    @classmethod
    def _decimal_strings(cls, values: list[str]) -> list[str]:
        for v in values:
            try:
                Decimal(v)
            except InvalidOperation as exc:
                raise ValueError("chart value is not a decimal string") from exc
        return values


class Chart(_Closed):
    type: Literal["chart"]
    chart_type: Literal["bar", "line"]
    title: StrictStr
    labels: list[StrictStr]
    series: Annotated[list[ChartSeries], Field(min_length=1)]

    @model_validator(mode="after")
    def _one_value_per_label(self) -> "Chart":
        if any(len(s.values) != len(self.labels) for s in self.series):
            raise ValueError("each chart series needs one value per label")
        return self


class Placeholder(_Closed):
    """Left for the analyst. It has no value field on purpose."""

    type: Literal["placeholder"]
    kind: Literal["rating", "target", "guidance"]


Block = Annotated[Heading | Paragraph | Bullets | Table | Chart | Placeholder, Field(discriminator="type")]


class Unit(_Closed):
    """A section of a Word report or a slide of a presentation."""

    title: StrictStr
    blocks: list[Block]


class Draft(_Closed):
    schema_version: Literal[1]
    format: Literal["word", "ppt"]
    units: list[Unit]


def _texts(draft: Draft) -> list[str]:
    out: list[str] = []
    for unit in draft.units:
        out.append(unit.title)
        for b in unit.blocks:
            if isinstance(b, Heading | Paragraph):
                out.append(b.text)
            elif isinstance(b, Bullets):
                out.extend(b.items)
            elif isinstance(b, Table):
                out.extend(b.header)
                out.extend(c for row in b.rows for c in row)
            elif isinstance(b, Chart):
                out.append(b.title)
                out.extend(b.labels)
                out.extend(s.name for s in b.series)
    return out


def draft_text(draft: Draft) -> str:
    """All the text of a draft in one string, for number checks."""
    return chr(10).join(_texts(draft))


def parse_draft(obj: dict[str, Any]) -> Draft:
    """Validate a draft. Limits come from settings. Raises DraftError; the error never repeats draft text."""
    if not isinstance(obj, dict):
        raise DraftError("draft must be an object")
    try:
        draft = Draft.model_validate(obj)
    except ValidationError as exc:
        where = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}" for e in exc.errors()[:5])
        raise DraftError(f"invalid draft ({where})") from None
    cfg = get_settings()
    if len(draft.units) > cfg.draft_max_units:
        raise DraftError("too many units")
    if sum(len(u.blocks) for u in draft.units) > cfg.draft_max_blocks:
        raise DraftError("too many blocks")
    if any(len(t) > cfg.draft_max_text_chars for t in _texts(draft)):
        raise DraftError("text too long")
    return draft


def to_json(draft: Draft) -> dict[str, Any]:
    return draft.model_dump(mode="json")
