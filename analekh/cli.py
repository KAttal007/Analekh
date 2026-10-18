"""Operator command line (design doc 19.3, 22.4).

analekh universe load [--file EQUITY_L.csv]   analekh search QUERY
analekh universe sectors [--stocks-file X]   (Stocks workbook, or curated map + index lists)
analekh watch SYMBOL | unwatch SYMBOL | watchlist
analekh refresh SYMBOL                        analekh backfill [SYMBOL]
analekh template add PATH --name N --sectors NBFC,Gold Finance [--from-model]
analekh template test TEMPLATE_ID SYMBOL      analekh template activate TEMPLATE_ID
analekh build SYMBOL [--template-id N] [--accept-all] [--out model.xlsx]
analekh sync MODEL_ID FILING_ID               analekh golden-test [--report golden.json]
"""

from pathlib import Path

import typer

app = typer.Typer(help="Analekh: the analyst's record, kept for you.", no_args_is_help=True)
universe_app = typer.Typer(help="Company universe (every NSE-listed company).")
template_app = typer.Typer(help="Model templates by sector.")
app.add_typer(universe_app, name="universe")
app.add_typer(template_app, name="template")


def _session():  # type: ignore[no-untyped-def]
    from analekh.db.session import session_scope

    return session_scope()


def _store():  # type: ignore[no-untyped-def]
    from analekh.ingest.storage import default_store

    return default_store()


def _company(s, symbol: str):  # type: ignore[no-untyped-def]
    from analekh.universe.search import get

    c = get(s, symbol)
    if c is None:
        raise typer.BadParameter(f"{symbol} is not in the universe; run `analekh universe load`")
    return c


@universe_app.command("load")
def universe_load(
    file: Path | None = typer.Option(None, help="EQUITY_L.csv downloaded by hand"),
    sme_file: Path | None = typer.Option(None, help="SME equity list CSV"),
) -> None:
    """Load or refresh the universe from files, or from NSE's published CSVs."""
    from analekh.universe.loader import parse_equity_list, refresh_from_nse, upsert_universe

    with _session() as s:
        if file:
            listed = parse_equity_list(file.read_bytes())
            if sme_file:
                listed += parse_equity_list(sme_file.read_bytes(), is_sme=True)
            summary = upsert_universe(s, listed)
        else:
            summary = refresh_from_nse(s)
    typer.echo(
        f"inserted {len(summary.inserted)}, updated {len(summary.updated)}, "
        f"renamed {len(summary.renamed)}, deactivated {len(summary.deactivated)}"
    )


@universe_app.command("sectors")
def universe_sectors(
    stocks_file: Path | None = typer.Option(
        None, help="Workbook converted with Excel's Stocks data type (Sector + ISIN No columns)"
    ),
    worksheet: Path | None = typer.Option(
        None, help="Your confirmed sectors (Symbol, Sector, Confirmed columns); no download"
    ),
) -> None:
    """Fill sectors: from a Stocks workbook, your worksheet, or the curated map then NSE Indices'
    lists."""
    from analekh.universe.sectors import (
        import_sector_worksheet,
        import_stocks_workbook,
        refresh_sectors,
    )

    if worksheet:
        with _session() as s:
            r = import_sector_worksheet(s, worksheet)
        typer.echo(
            f"{r['rows']} rows, {r['confirmed']} confirmed, {r['updated']} sectors set"
            + (
                f", {r['not_an_nse_sector']} skipped (not an NSE sector)"
                if r["not_an_nse_sector"]
                else ""
            )
        )
        return
    if stocks_file:
        with _session() as s:
            w = import_stocks_workbook(s, stocks_file)
        typer.echo(
            f"{w['rows']} rows, {w['with_sector']} with a sector, {w['matched']} matched by ISIN, "
            f"{w['updated']} sectors changed"
        )
        return
    with _session() as s:
        r = refresh_sectors(s)
    typer.echo(
        f"lists {r['lists_fetched']}/{r['lists_total']}, {r['companies_listed']} companies listed "
        f"({r['banks']} banks); sectors set: {r['updated_curated']} curated, "
        f"{r['updated_from_lists']} from lists"
    )


@app.command()
def search(query: str, limit: int = 15) -> None:
    from analekh.universe.search import search as do_search

    with _session() as s:
        for h in do_search(s, query, limit):
            typer.echo(f"{h.nse_symbol:<14} {h.name}  {h.sector or ''}")


@app.command()
def watch(symbol: str) -> None:
    from analekh import coverage

    with _session() as s:
        coverage.add(s, _company(s, symbol))
    typer.echo(f"{symbol.upper()} added to the watchlist")


@app.command()
def unwatch(symbol: str) -> None:
    from analekh import coverage

    with _session() as s:
        coverage.remove(s, _company(s, symbol))
    typer.echo(f"{symbol.upper()} removed from the watchlist")


@app.command()
def watchlist() -> None:
    from analekh import coverage

    with _session() as s:
        for w in coverage.entries(s):
            typer.echo(f"{w.company.nse_symbol:<14} {w.company.name}")


@app.command()
def refresh(symbol: str) -> None:
    """Fetch, parse and validate the newest results filing (runs inline)."""
    from analekh.jobs.tasks import refresh_company

    typer.echo(refresh_company(symbol))


@app.command("results-watch")
def results_watch(
    force: bool = typer.Option(False, "--force", help="Ask NSE now, whatever the schedule."),
) -> None:
    """New results for every company from ONE request to NSE's latest list: every 2 hours from
    09:00 to 23:00 IST in a results season, once a day at 21:00 otherwise (design doc 9.6)."""
    from analekh.jobs.tasks import watch_results

    typer.echo(watch_results(force))


@app.command("prices")
def prices(
    day: str | None = typer.Option(
        None, "--date", help="Trading day (YYYY-MM-DD); default: latest close."
    ),
    recompute: bool = typer.Option(
        False, help="Recompute market caps of the stored prices only (no download)."
    ),
) -> None:
    """Closing prices for every company from NSE's bhavcopy (ONE request; skipped if stored)."""
    if recompute:
        from analekh.ingest.bhavcopy import recompute_market_caps

        with _session() as s:
            typer.echo(recompute_market_caps(s))
        return
    from analekh.jobs.tasks import fetch_prices

    typer.echo(fetch_prices(day))


@app.command("results-backfill")
def results_backfill(
    symbols: str | None = typer.Option(
        None, help="Comma-separated tickers; default: every company with a sector."
    ),
    limit: int | None = typer.Option(None, help="Stop after this many companies."),
    quarters: int = typer.Option(8, help="Newest N quarters per company."),
    one_basis: bool = typer.Option(
        False, help="One basis per quarter (consolidated when filed); default: both."
    ),
    redo: bool = typer.Option(False, help="Include companies that already have results filings."),
    interval: float | None = typer.Option(
        None, help="Seconds between requests to NSE (default: DOWNLOAD_RATE_PER_SECOND)."
    ),
    start_at: str | None = typer.Option(
        None, help="Resume at this ticker (inclusive), e.g. the one NSE stalled on."
    ),
    recheck_no_filings: bool = typer.Option(
        False, help="Check again the companies no-filings.csv lists as having nothing on NSE."
    ),
    history: bool = typer.Option(
        False, help="Results from before integrated filings (XBRL from 2018), for every company."
    ),
    sector: list[str] = typer.Option(
        None, help='Only this sector; repeat for several (--sector "Oil & Gas" --sector ...).'
    ),
) -> None:
    """Fetch results XBRL from NSE's integrated filings for many companies (resumable)."""
    from analekh.jobs.tasks import bulk_fetch_results

    result = bulk_fetch_results(
        [x.strip() for x in symbols.split(",")] if symbols else None,
        limit=limit,
        quarters=quarters,
        one_basis=one_basis,
        skip_done=not redo,
        interval_seconds=interval,
        start_at=start_at,
        skip_no_filings=not recheck_no_filings,
        history=history,
        sectors=sector or None,
    )
    typer.echo(result)


AUDIO_SUFFIXES = {".mp3", ".m4a", ".mp4", ".wav", ".webm", ".aac", ".ogg", ".flac"}


@app.command("transcribe-audio")
def transcribe_audio(
    symbol: str,
    files: list[Path] = typer.Argument(None, help="Recordings; default: IMPORT_DIR/<SYMBOL>/."),
    model: str = typer.Option("large-v3", help="Whisper model (large-v3, medium, small...)."),
    out_dir: Path = typer.Option(Path("out/audio"), help="Where the text and JSON go."),
) -> None:
    """Earnings-call recordings to timestamped text (needs ``uv sync --group audio``)."""
    from analekh.config import get_settings
    from analekh.docs.audio import transcribe

    symbol = symbol.upper()
    if not files:
        folder = Path(get_settings().import_dir) / symbol
        files = sorted(f for f in folder.glob("*") if f.suffix.lower() in AUDIO_SUFFIXES)
        if not files:
            raise typer.BadParameter(f"no recordings in {folder}")
    company = None
    try:
        from sqlalchemy import select

        from analekh.db.models import Company

        with _session() as s:
            company = s.scalar(select(Company.name).where(Company.nse_symbol == symbol))
    except Exception:  # noqa: BLE001 - the name only sharpens the vocabulary hint
        pass
    target = out_dir / symbol
    target.mkdir(parents=True, exist_ok=True)
    for path in files:
        result = transcribe(path, company=company, model=model)
        (target / f"{path.stem}.json").write_text(result.to_json(), encoding="utf-8")
        (target / f"{path.stem}.txt").write_text(result.text(), encoding="utf-8")
        unsure = sum(1 for x in result.segments if x.avg_logprob < -1.0)
        typer.echo(
            f"{path.name}: {result.duration / 60:.0f} min of audio in {result.seconds_taken:.0f} s "
            f"on {result.device}, {len(result.segments)} segments ({unsure} low-confidence) "
            f"-> {target / path.stem}.txt"
        )


@app.command("recompute-latest")
def recompute_latest(
    symbols: list[str] = typer.Argument(None, help="Tickers; default: every company with results."),
) -> None:
    """Use the newest FILED value of every line (revised filings beat originals whatever order
    they were downloaded in) and label refiled quarters. Database only: downloads nothing."""
    from sqlalchemy import exists, select

    from analekh.db.models import Company, Filing
    from analekh.ingest.pipeline import refresh_latest
    from analekh.restatements import infer_revision_flags

    with _session() as s:
        q = select(Company.id, Company.nse_symbol).where(
            exists().where(Filing.company_id == Company.id, Filing.kind == "results_xbrl")
        )
        if symbols:
            q = q.where(Company.nse_symbol.in_([x.upper() for x in symbols]))
        todo = list(s.execute(q.order_by(Company.nse_symbol)))
    changed = labelled = 0
    for company_id, symbol in todo:
        with _session() as s:
            labelled += infer_revision_flags(s, company_id)
            n = refresh_latest(s, company_id)
        changed += n
        if n:
            typer.echo(f"{symbol}: {n} values switched")
    typer.echo(
        f"{len(todo)} companies: {changed} values switched to the newest filing, "
        f"{labelled} filings labelled original or revision"
    )


@app.command()
def revalidate(
    symbols: list[str] = typer.Argument(None, help="Tickers; default: every company with results."),
) -> None:
    """Re-run format detection and V1-V10 on stored results files (no downloads)."""
    from sqlalchemy import exists, select

    from analekh.db.models import Company, Filing
    from analekh.ingest.pipeline import revalidate_company

    store = _store()
    with _session() as s:
        q = select(Company.nse_symbol).where(
            exists().where(Filing.company_id == Company.id, Filing.kind == "results_xbrl")
        )
        if symbols:
            q = q.where(Company.nse_symbol.in_([x.upper() for x in symbols]))
        todo = list(s.scalars(q.order_by(Company.nse_symbol)))
    for symbol in todo:
        with _session() as s:
            company = s.scalar(select(Company).where(Company.nse_symbol == symbol))
            assert company is not None
            filings = revalidate_company(s, store, company)
            blocked = sum(bool((f.meta or {}).get("blocks_auto_apply")) for f in filings)
            typer.echo(
                f"{symbol}: {company.results_taxonomy}, {len(filings)} filings, {blocked} blocked"
            )


@app.command()
def backfill(symbol: str | None = typer.Argument(None)) -> None:
    """Ingest files from IMPORT_DIR/<SYMBOL>/ through the normal parser and validation path."""
    from analekh.jobs.tasks import backfill as do_backfill

    result = do_backfill(symbol)
    typer.echo(
        f"ingested {len(result['ingested'])}, skipped {len(result['skipped'])}, "
        f"unknown symbols {result['unknown_symbols']}"
    )


@template_app.command("add")
def template_add(
    path: Path,
    name: str = typer.Option(...),
    sectors: str = typer.Option(...),
    owner: str = "local",
    from_model: bool = False,
) -> None:
    from analekh.templates.onboarding import upload

    with _session() as s:
        t = upload(
            s,
            _store(),
            path.read_bytes(),
            name=name,
            owner=owner,
            sectors=[x.strip() for x in sectors.split(",")],
            from_existing_model=from_model,
        )
        low = [r for r in (t.mapping or {}).get("rows", []) if r.get("confidence", 1) < 0.8]
        typer.echo(
            f"template {t.id} v{t.version} ({t.status}); "
            f"{len((t.mapping or {}).get('rows', []))} rows mapped, {len(low)} to review"
        )


@template_app.command("test")
def template_test(template_id: int, symbol: str) -> None:
    from analekh.db.models import Template
    from analekh.templates.testbuild import run_test_build

    with _session() as s:
        t = s.get(Template, template_id)
        if t is None:
            raise typer.BadParameter("template not found")
        test = run_test_build(s, _store(), t, _company(s, symbol))
        typer.echo(f"{test.result}: {test.issues}")


@template_app.command("activate")
def template_activate(template_id: int, default: bool = False) -> None:
    from analekh.db.models import Template
    from analekh.templates.onboarding import activate

    with _session() as s:
        t = s.get(Template, template_id)
        if t is None:
            raise typer.BadParameter("template not found")
        activate(s, t, default)
        typer.echo(f"template {t.id} active")


@app.command()
def build(
    symbol: str, template_id: int | None = None, accept_all: bool = False, out: Path | None = None
) -> None:
    """Start coverage: build a model from a template with sourced history."""
    from sqlalchemy import select

    from analekh.builder.coverage import finalize_build, start_coverage
    from analekh.db.models import Assumption, ModelVersion, Template
    from analekh.templates.onboarding import default_for, ensure_builtin_templates

    store = _store()
    with _session() as s:
        company = _company(s, symbol)
        ensure_builtin_templates(s, store)
        template = (
            s.get(Template, template_id)
            if template_id
            else default_for(s, company.industry or company.sector) or default_for(s, None)
        )
        if template is None:
            raise typer.BadParameter("no active template")
        res = start_coverage(s, store, company, template)
        typer.echo(
            f"model {res.model.id}: {len(res.fill.written)} inputs filled; "
            f"rows not reported: {res.fill.blank_rows}"
        )
        for p in res.proposals:
            typer.echo(f"  {p.driver}: {p.value}  {p.rationale}")
        if not accept_all:
            typer.echo("Review assumptions in the web app, then POST /models/{id}/finalize.")
            return
        for a in s.scalars(select(Assumption).where(Assumption.model_id == res.model.id)):
            a.decision, a.final_value = "accepted", a.proposed_value
        done = finalize_build(s, store, res.model, created_by="cli")
        typer.echo(f"build {done.build.status}; checks passed: {done.checks.passed}")
        if out and done.version:
            mv = s.get(ModelVersion, done.version.id)
            assert mv is not None
            out.write_bytes(store.get(mv.storage_key))
            typer.echo(f"saved {out}")


@app.command()
def sync(model_id: int, filing_id: int) -> None:
    """Build a change set for a linked model from a filing (runs inline)."""
    from analekh.jobs.tasks import sync_model

    typer.echo(sync_model(model_id, filing_id))


@app.command("golden-test")
def golden_test(
    report: Path = typer.Option(Path("golden.json")),
    folder: Path = typer.Option(Path("tests/fixtures/golden")),
) -> None:
    """Exact-match accuracy on hand-checked filings (design doc 24)."""
    from analekh import golden

    result = golden.run(folder)
    golden.write(result, report)
    typer.echo(
        f"fixtures {result.fixtures}, checked {result.checked}, matched {result.matched}"
        f"{' - ' + result.note if result.note else ''}"
    )
    for m in result.mismatches:
        typer.echo(f"  {m.file} {m.element} {m.period_end}: PDF {m.expected}, parsed {m.actual}")
    if result.checked and not result.passed:
        raise typer.Exit(1)


@app.command("golden-sheet")
def golden_sheet(
    folder: Path = typer.Option(Path("tests/fixtures/golden")),
    force: bool = typer.Option(False, help="Replace a worksheet that may hold answers"),
) -> None:
    """Worksheet for the golden-set hand-check: 20 filings' XBRL from storage (no downloads)."""
    from analekh import golden

    with _session() as s:
        try:
            out, built, missing = golden.build_sheet(s, _store(), folder, force=force)
        except FileExistsError as e:
            raise typer.BadParameter(str(e)) from e
    lines = sum(len(f.lines) for f in built)
    typer.echo(f"{out}: {len(built)} filings, {lines} lines to check")
    for p in missing:
        typer.echo(f"  not in the database: {p.symbol} {p.period_end} {p.format}")


@app.command("golden-import")
def golden_import(folder: Path = typer.Option(Path("tests/fixtures/golden"))) -> None:
    """Write the golden set's manifest.yaml from the marked worksheet."""
    from analekh import golden

    r = golden.import_sheet(folder)
    typer.echo(
        f"confirmed {r.confirmed}, corrected {r.corrected}, not in PDF {r.not_in_pdf}, "
        f"still to mark {r.pending}"
    )
    for problem in r.problems:
        typer.echo(f"  {problem}")


if __name__ == "__main__":
    app()
