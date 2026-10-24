# Pending items

Open work, checked against CLAUDE.md ("Where the skeleton stops") and the model-locks work.
Tick a box when it is done. Items marked *status unknown* have not been confirmed.

## Owner actions

- [ ] Two-browser check for model locks: lock and 423, read-only view, toast and chime, stale apply refusal, blocked-filing pop-up, idle and sign-in reminders
- [ ] Confirm Update drafts from the newest non-blocked filing (the rule we built)
- [ ] Review section 8 of `docs/superpowers/specs/2026-10-22-auth-roles-locks-design.md` (model locks)
- [ ] Golden set: run `uv run analekh golden-sheet`, mark the filings against the results PDFs, then `golden-import` and `golden-test`

## Data and mapping

- [ ] Sector mapping: run the index list importer (`universe/sectors.py`); `data/sector_map.csv` holds overrides only
- [ ] SME list path: confirm it in `universe/loader.py`
- [ ] Fill `universe/data/nifty500.csv` (backfill priority list, still empty)
- [ ] Verify XBRL element names marked `# verify` in `xbrl/elements.py` against real filings; run `analekh revalidate` after changes
- [ ] Map the insurers' balance sheet (not mapped yet)

## Templates and backfill

- [ ] Balance sheet and cash flow in `templates_builtin/specs.py` (currently P&L and KPIs only); needs the annual backfill

## Pipeline and GenAI

- [ ] Wire V10 (XBRL wins over AI-extracted values) into `docs/pipeline.py`
- [ ] Decide the embeddings provider (open question 28.7)
- [ ] Unprocessed feed items: about 290 items from issuers outside the universe (mostly debt-only or unlisted) are never picked up, since the queue needs a matched company. They inflate the "unprocessed" column in `admin/app.py`. Proposed: count only matched items there and leave the rest in "unlinked" (not decided). Review the list in `out/unmatched_feed_items.csv` for companies worth adding to the universe

## Valuation

- [ ] Source debt and cash for `ib/comps.py` so EV multiples are filled in
- [ ] Map insurers' book value for `ib/comps.py`

## Architecture

- [ ] Move reports from inline API execution to Celery jobs, storing files in object storage

## Status unknown (confirm)

- [ ] Whether any of the items above were finished outside this session
