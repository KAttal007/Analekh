# Reported NIM and funding ratios from investor decks (built 2026-10-31; OCR and other sources to come)

Status: built (2026-10-31): `analekh/decks/` (reader, entities, ratios), `analekh/ingest/decks.py`, tables
`reported_ratios` and `investor_decks`, desk NIM and cost of funds. Tested on 44 lenders' Q2 FY27 decks
first. Not ported: OCR of image-only pages (`nim_ocr.py` in the session scratchpad; 33 of 37 values matched).

## Why

XBRL carries no NIM or funding ratios. Lenders print them in the investor presentation, the concall and
the annual report. The desk's computed NIM (`interest.py`) differs from reported NIM by 0.34 points on
average and up to 2.1 (n=54), because lenders divide by average total assets or AUM and we divide by
interest-earning assets.

## Owner's decisions (2026-10-31)

1. **Reported first.** For a company and quarter, use the reported figure if any source has it (deck, then
   concall, then annual report). Only when none has it after every method, show the computed figure, with a
   tooltip saying why it can differ from the company's own (its base may be average total assets or AUM;
   ours is average interest-earning assets). Never show both together. Show the computed fallback for NBFCs
   and housing finance companies too.
2. **Yield has no derived fallback.** Missing yield is the computed yield on average earning assets
   (`interest.py`), not NIM + cost of funds (that sat 0.2 to 2.3 points off the reported yield).
3. **Changes compare like with like.** A YoY or QoQ change is shown only when both quarters come from the
   same source (reported with reported, computed with computed).
4. **Entities.** Bajaj Finance: consolidated pick shows the consolidated section (Q2 FY27 cost of funds
   7.31%), standalone shows the company's own section (7.40%). Bajaj Housing Finance's figures (7.04%) are
   stored against BAJAJHFL, from the same deck.
5. **Coverage starts at FY23.** Older history in a deck is real but not stored.
6. **Source:** NSE `/api/corporate-announcements` (owner-approved 2026-10-31). Rule 1 and `ALLOWED_PATHS`
   are NOT yet amended; the daily limit is still to be set (proposed: once a day at 21:30 IST, one list
   request with no symbol, then one PDF per new deck of a lender we cover, from `nsearchives`).

## What the reader does (all rule-based, no LLM; OCR is the project's own RapidOCR)

- **Quarter labels** in any notation resolve to a quarter end (Indian fiscal year): `Q2FY27`, `Q2 FY2027`,
  `Q2-2027`, `2QFY27`, `Sep'26`, `Sep-26`, `September 30, 2026`, `30.09.2026`, `Jul-Sep'26`, a bare `Q2` with the
  deck's own year. Half-year (`H1FY27`, `HY1`), `9M`, full-year, cumulative, YTD, "as on", "actuals", guidance,
  "yearly", "(6 M)" are rejected, never averaged or stored.
- **Metric label** accepts "Net Interest Margin" and "NIM" (and the same for each ratio). It rejects risk
  adjusted, core, excluding, impact, dilutive, forecasts ("estimate", "guidance", "expected").
- **Layers:** sentence (value and quarter in one clause, or the page title's quarter); table (ruled, by
  position, prose cell under "Q2 FY27 vs Q2 FY26", rows merged into one cell, quarters down a column); chart
  (bars; one line; several lines told apart by the legend's colour; a metric named only in the legend, as
  Bank of Maharashtra's NII bars with a NIM line); KPI card (the value must sit in the label's own drawn
  box); OCR of the page image with the same rules (33 of 37 values matched, 0 wrong).
- **Basis** is kept per value: whole bank, domestic, global, consolidated, standalone, "excl. adjustment",
  a stated method ("on daily average basis", "opening and closing average basis"), segment. Only the
  headline bases are stored as the company's figure.
- **Entities:** each page is tagged with the section its title names (a company is matched to our table by
  name or initials, so `BHFL` is BAJAJHFL); pages about subsidiaries, associates or sponsored banks are
  never the company's own; "group financials" is the consolidated company; an untitled page does not inherit
  another entity.
- **Conflicts:** two different values for one quarter, entity and basis are not stored, except that an
  explicit "Quarterly" column wins over a chart (Canara's chart showed cumulative values). A page an explicit
  quarterly column overruled is dropped for every metric.

## Results on 44 lenders

NIM was read for most of the 44 decks and the other ratios for fewer (many decks print only NIM). Exact
per-metric tallies on the final code were not taken: rerun them when the reader is built. On the last
regression the company's own figures matched the previous verified run in 204 of 204 cases, with 22 more
values added, each checked on its slide. Bajaj Finance's deck states no NIM (net interest income only; "NIM"
appears only in the glossary): its NIM must come from the concall or annual report. Computed NIM vs reported:
mean gap 0.34 points, up to 2.1 (n=54). Sample is one quarter and 44 lenders: hit rates will move with more
decks.

## Known gaps

- Fixed 2026-10-31, each checked on its slide: Cholamandalam's segment P&L pages ("Profit and Loss Statement
  - <business>") were read as the company's own, which made the four cost-of-funds conflicts; IOB's titles
  are centred over their charts and the values sit in small tags; ESAF's shared title ends in "and". The
  changes were not re-run across all 44 decks (the files were deleted): re-fetch and compare before
  trusting hit rates.
- Decks with no NIM: Tata Capital, Kissht, MAS Financial (none printed); PFS, Manba (half-year only).
- Not built: OCR of image-only pages, concalls and annual reports as sources (Bajaj Finance prints no NIM in
  its deck), other quarters (Q4 decks carry full-year columns).

## Built

Daily limit: none of its own. The announcements list is fetched by the results watcher, in the same run, on
its schedule (hourly in season, 21:00 otherwise). A failure there never fails the results run.
