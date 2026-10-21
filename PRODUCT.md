# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Equity research and investment banking analysts covering NSE-listed companies. They work fast, desktop-first, during results seasons, checking who has reported and updating their Excel models. A phone is secondary.

## Product Purpose

Any NSE-listed company in; validated XBRL facts, a built or updated Excel model (analyst-approved) and grounded research drafts out. Success is that an analyst trusts the numbers, sees what is new, and spends their time on judgement, not data entry.

## Positioning

Figures are read from the filings themselves and checked before they reach the analyst; nothing writes to a model without approval; generated text only contains numbers from tool results. No ratings or target prices.

## Operating Context

Results seasons set by SEBI (45 days after a quarter, 60 after the year). Analysts live in Excel; the web app is the results desk, watchlist, comps and model review beside it. Data comes only from NSE's published feeds and approved lookups (CLAUDE.md rule 1).

## Capabilities and Constraints

- Web app (`web/`, React + TypeScript) and an Excel task pane (`office-addin/`).
- Motion is for what the user clicks (tabs, switches, selections); data and screens appear instantly (owner's rule, 2026-10-17).
- Lightweight additions preferred; keep Inter, AG Grid, ECharts.
- Money is shown from Decimal/NUMERIC values; Indian number formatting and IST.
- Undecided: whether concall dates become available (needs an NSE access approval).

## Brand Commitments

Name: Analekh. Tagline: "The analyst's record, kept for you." One accent blue, light and dark themes.

## Evidence on Hand

Real filings in storage; golden set under `tests/fixtures/golden/` (gitignored). No customer testimonials or usage data exist; do not invent any.

## Product Principles

1. Trust over flair: every number is sourced and checked.
2. The analyst approves; the product proposes.
3. Dense and scannable beats decorative.
4. Motion answers a click, never decorates data.
5. Stay within NSE's published access.
