# Sectors from Excel's Stocks data type

How Analekh gets a sector for most listed companies. First run on 2026-10-13: 2,458 of 2,606 NSE
main-board companies.

NSE's equity list has no sector column, and neither do results filings. Excel's **Stocks** data
type (data from LSEG, through Microsoft 365) does: its **Industry** field gives the LSEG industry
group, such as *Software & IT Services* or *Banking Services*. BSE's securities list supplies an
unambiguous ID for each company, so Excel matches every row to the right listing.

## What you need

- A **Microsoft 365** account. Office 2019, 2021 and 2024 don't have the Stocks data type. Excel
  for the web works, including with a college account.
- BSE's **List of Securities**, downloaded by hand from bseindia.com (Equity, all statuses). It's
  saved as `Equity.csv`.
- Analekh's database running, with the universe loaded (`uv run analekh universe load`).

## Steps

### 1. Build the workbook

```bash
uv run python scripts/stocks_workbook.py bse D:/Downloads/Equity.csv D:/Downloads/Equity_active.xlsx
```

This keeps only active company shares. It drops delisted and suspended securities, mutual fund
ETFs (BSE lists them as Equity), rights entitlements and preference shares. It also adds two
columns in front:

| Column | Contains |
|---|---|
| A **Sector** | `=IFERROR(FIELDVALUE(B2,"Industry"),"")`, blank until column B is converted |
| B **BSE Stock ID** | `XBOM:` + BSE security code, e.g. `XBOM:500325` for Reliance |

`XBOM` is BSE's exchange code. Using it with the security code points to exactly one listing,
whereas a bare ticker like `TCS` could also match a foreign security.

**NSE version.** The same workbook for every active NSE company (main board and SME), with
`XNSE:` + NSE symbol in column B, from Analekh's universe; no BSE file needed:

```bash
uv run python scripts/stocks_workbook.py nse D:/Downloads/NSE_active.xlsx
```

Add `--equity-csv EQUITY_L.csv` to build it from NSE's equity list downloaded by hand instead.
It covers the NSE SME companies the BSE file misses.

### 2. Convert the IDs in Excel

1. Open the workbook in Microsoft 365 Excel. For Excel for the web, upload it to OneDrive first.
2. Select the IDs in column B (click B2, then Ctrl+Shift+↓).
3. Go to **Data → Data Types → Stocks**. Recognised IDs get a stock icon, and column A fills with
   the industry. Excel shows the formula as `=@IFERROR(...)`; the `@` is harmless.
4. Rows Excel doesn't recognise show a **?**. Pick the company in the side panel, or delete the
   row.
5. Save, or use **Download a copy** in Excel for the web.

### 3. Import into Analekh

```bash
uv run analekh universe sectors --stocks-file "D:/Downloads/Equity_active (1).xlsx"
```

The import matches rows to companies by **ISIN**. It reads the cached value of column A, so
column B can stay converted. Blank rows and rows showing an Excel error are skipped. The command
prints how many rows it read, matched and updated.

### 4. Fill the rest

Companies not on BSE, including all NSE SME companies, need NSE IDs instead:

```bash
uv run python scripts/stocks_workbook.py remaining D:/Downloads/Sectors_remaining.xlsx
```

This lists every active company still without a sector, with `XNSE:` + NSE symbol in column B.
Repeat steps 2 and 3 with it.

### 5. Set the last ones by hand

Companies Excel can't recognise at all (168 on 2026-10-18, mostly former SME companies and new
listings) get a sector from a worksheet: Symbol, Sector (one of NSE's 22) and Confirmed columns.
Mark each row you agree with as `Yes`, correcting the sector first where needed, then:

```bash
uv run analekh universe sectors --worksheet out/sector-worksheet.xlsx
```

Confirmed rows go into `analekh/universe/data/sector_map.csv` as your own sectors (source
`user`), which no other source replaces. Unconfirmed rows are left alone, so the worksheet can be
imported in several passes. Nothing is downloaded.

## How Analekh uses the result

- **Recorded source:** every sector imported this way is stored with `sector_source =
  excel_stocks` (migration 0002).
- **Precedence:** sources rank **user > excel_stocks > nse_indices**. A lower source never
  replaces a higher one, and re-importing a newer workbook refreshes earlier Stocks values. A
  sector set by hand is never overwritten.
- **No filing type:** Stocks sectors never set a company's filing type (bank, NBFC, insurance,
  Ind-AS). LSEG's *Banking Services* group also contains NBFCs such as Bajaj Finance and
  Muthoot. The first parsed filing's XBRL schema decides the filing type instead.

## How often

Every few months, or before you start covering companies that listed recently. New listings
have no sector until the next refresh.

## Data terms

The Stocks data is licensed to the Microsoft 365 account holder for their own use. It's fine
for your own research database. Don't commit the workbooks to git (keep them outside the repo),
and don't republish the sectors. A public or commercial product would need its own data
licence, for example from LSEG or C-MOTS.
