"""Reported ratios of one investor deck: the reader's readings, resolved to the figures we store.

The reader (`reader.py`) returns every reading with its quarter, basis, entity, page and layer. This
module decides what is kept (design: docs/superpowers/specs/2026-10-31-deck-ratios-design.md):

- one value per company, quarter, metric and basis group ('all', 'consolidated', 'standalone');
- readings that agree are stored; an explicit "Quarterly" column wins over a chart; any other
  disagreement stores nothing (we do not guess);
- a page that an explicit quarterly column overruled for NIM is dropped for every metric;
- a section about a subsidiary of the deck's company is stored against that company when we have it
  (Bajaj Housing Finance inside Bajaj Finance's deck); segments and unknown entities are not stored.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from analekh.decks import entities, reader

METRICS = ("nim", "cof", "cod", "yield_adv", "yield_assets", "yield_funds")
BASIS_GROUPS = {"unspecified": "all", "whole bank": "all", "global": "all", "consolidated": "consolidated", "standalone": "standalone"}

_LOCK = threading.Lock()  # the reader keeps its current metric in module state: one deck at a time


@dataclass(frozen=True)
class Ratio:
    symbol: str
    period_end: date
    metric: str
    basis: str  # 'all' | 'consolidated' | 'standalone'
    value: Decimal
    page: int
    layer: str


def _resolve(readings: list[dict], tainted: set[int]) -> tuple[list[tuple], set[int]]:
    """([(entity, quarter, basis_group, value, page, layer)], pages overruled by an explicit quarterly column)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for f in readings:
        group = BASIS_GROUPS.get(f["basis"])
        if group is None or "forecast-word" in f["flags"] or f["page"] in tainted:
            continue
        entity = f.get("entity", "self")
        if entity.startswith("other:"):
            continue
        groups[(entity, f["quarter"], group)].append(f)
    kept: list[tuple] = []
    overruled: set[int] = set()
    for (entity, quarter, group), cands in groups.items():
        values = {round(f["value"], 2) for f in cands}
        chosen = cands
        if len(values) > 1:
            explicit = [f for f in cands if "explicit-quarterly" in f["flags"]]
            if len({round(f["value"], 2) for f in explicit}) != 1:
                continue  # a real disagreement: store nothing
            chosen = explicit
            wanted = round(explicit[0]["value"], 2)
            overruled |= {f["page"] for f in cands if round(f["value"], 2) != wanted}
        pick = min(chosen, key=lambda f: f["page"])
        kept.append((entity, quarter, group, round(pick["value"], 2), pick["page"], pick["layer"]))
    return kept, overruled


def read_deck(pdf_path: Path, symbol: str, names: dict[str, str]) -> list[Ratio]:
    """Every ratio we can store from one deck. `names` maps symbol -> company name (our companies table)."""
    out: list[Ratio] = []
    tainted: set[int] = set()
    with _LOCK:
        entities.set_names(names)
        for metric in METRICS:
            reader.use_metric(metric)
            kept, overruled = _resolve(reader.run(pdf_path, symbol), tainted)
            if metric == "nim":
                tainted |= overruled  # a page caught showing cumulative NIM is cumulative for every metric
            for entity, quarter, group, value, page, layer in kept:
                target = symbol if entity == "self" else entity
                if target != symbol and target not in names:
                    continue
                out.append(Ratio(target, quarter, metric, group, Decimal(str(value)), page, layer))
    return out
