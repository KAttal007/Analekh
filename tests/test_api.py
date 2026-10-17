"""API flows over HTTP (design doc 20) on PostgreSQL with a local object store. SYNTHETIC data."""

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.db.models import Company, Filing, Model
from analekh.db.session import get_session
from analekh.facts import DbValueSource
from analekh.ingest.pipeline import ingest_results_xbrl
from analekh.modelsync.changeset import build_change_set, save_proposal
from analekh.templates_builtin import NBFC
from analekh.templates_builtin import build as build_builtin
from analekh.universe.loader import parse_equity_list, upsert_universe
from analekh.workbook.mapping import Mapping
from tests.test_builder import QUARTERS, history
from tests.test_universe import EQUITY_L
from tests.xbrl_factory import BS, Q2, build_instance, pnl, quarter_instance

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def client(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def demo(db, store):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    c = db.scalar(select(Company).where(Company.nse_symbol == "DEMOFIN"))
    c.sector, c.industry = "Financial Services", "NBFC"
    for i, end in enumerate(QUARTERS):
        ingest_results_xbrl(db, store, c, quarter_instance(end, **history(i)))
    return c


def test_company_index_for_in_browser_search(client, demo):
    first = client.get("/companies/index")
    rows = {r["nse_symbol"]: r for r in first.json()}
    assert rows["DEMOFIN"] == {
        "id": demo.id,
        "nse_symbol": "DEMOFIN",
        "name": "Demo Finance Limited",
        "isin": "INE000D01011",
        "sector": "Financial Services",
    }
    etag = first.headers["ETag"]
    again = client.get("/companies/index", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.headers["ETag"] == etag


def test_search_company_page_and_watchlist(client, demo):
    hits = client.get("/companies/search", params={"q": "demo fin"}).json()
    assert hits[0]["nse_symbol"] == "DEMOFIN"
    page = client.get("/companies/demofin").json()
    assert page["coverage_level"] == "numbers" and not page["watched"]
    assert client.get("/companies/OLDCO").json()["coverage_level"] == "universe"
    assert client.get("/companies/NOPE").status_code == 404

    added = client.post("/watchlist", json={"symbol": "DEMOFIN", "settings": {"alerts": True}})
    assert added.json()["coverage_level"] == "deep"
    [entry] = client.get("/watchlist").json()
    assert entry["symbol"] == "DEMOFIN" and entry["last_filing"] == "2026-09-30"
    assert client.delete("/watchlist/DEMOFIN").status_code == 204
    assert client.get("/watchlist").json() == []

    filings = client.get("/companies/DEMOFIN/filings").json()
    assert filings[0]["period_end"] == "2026-09-30" and len(filings) == 8
    facts = client.get(
        "/companies/DEMOFIN/facts",
        params={"elements": "RevenueFromOperations", "start": "2026-09-30"},
    ).json()
    assert [f["value"] for f in facts] == ["975000000.0000"]


def test_facts_fall_back_to_standalone_when_company_files_no_consolidated(client, db, store):
    solo = Company(nse_symbol="SOLO", name="Solo Systems Limited", isin="INE000S01011")
    db.add(solo)
    db.flush()
    q = pnl(500_000_000, 10_000_000, 400_000_000, 25_000_000)
    standalone = build_instance(**Q2, values_q=q, values_instant=BS, nature="Standalone")
    ingest_results_xbrl(db, store, solo, standalone)
    facts = client.get("/companies/SOLO/facts", params={"elements": "RevenueFromOperations"})
    assert {f["value"] for f in facts.json()} == {"500000000.0000"}  # quarter and YTD
    asked = client.get(
        "/companies/SOLO/facts", params={"elements": "RevenueFromOperations", "consolidated": True}
    )
    assert asked.json() == []


def test_start_coverage_assumptions_finalize_then_review_and_apply(client, db, store, demo):
    built = client.post("/coverage", json={"symbol": "DEMOFIN"}).json()
    assert built["build_status"] == "awaiting_assumptions" and built["filled_cells"] >= 32
    model_id = built["model"]["id"]
    assert client.post(f"/models/{model_id}/finalize").status_code == 409  # pending assumptions

    tax = next(a for a in built["assumptions"] if a["driver"] == "tax_rate")
    decided = client.post(
        f"/models/{model_id}/assumptions/decisions",
        json={
            "decisions": [{"id": tax["id"], "decision": "edited", "final_value": "0.25"}],
            "accept_all": True,
        },
    ).json()
    assert {a["decision"] for a in decided} == {"accepted", "edited"}
    done = client.post(f"/models/{model_id}/finalize").json()
    assert done["status"] == "built" and done["checks"]["passed"] and done["version"] == 1

    # Next results: change set on the built model, reviewed and applied as a new version.
    nxt = ingest_results_xbrl(db, store, demo, quarter_instance(date(2026, 12, 31), **history(8)))
    model = db.get(Model, model_id)
    v1 = client.get(f"/models/{model_id}/versions/1")
    proposal = build_change_set(
        load_workbook(io.BytesIO(v1.content)),
        Mapping.model_validate(model.mapping),
        date(2026, 12, 31),
        DbValueSource(db, demo.id),
        last_fingerprint=model.fingerprint,
    )
    cs = save_proposal(db, model_id, 1, nxt.filing.id, proposal)

    assert client.post(f"/change-sets/{cs.id}/apply").status_code == 409  # nothing decided
    items = client.get(f"/change-sets/{cs.id}").json()["items"]
    revenue = next(i for i in items if i["kind"] == "actual_write" and i["cell"] == "J3")
    r = client.post(
        f"/change-sets/{cs.id}/decisions",
        json={
            "accept_kinds": ["actual_write", "roll_forward", "label_shift"],
            "decisions": [{"item_id": revenue["id"], "decision": "edited", "final_value": "100.5"}],
        },
    )
    remaining = [i for i in r.json()["items"] if i["decision"] == "pending"]
    if remaining:
        r = client.post(
            f"/change-sets/{cs.id}/decisions",
            json={"decisions": [{"item_id": i["id"], "decision": "skipped"} for i in remaining]},
        )
    assert r.json()["status"] == "approved"
    applied = client.post(f"/change-sets/{cs.id}/apply").json()
    assert applied["version"] == 2
    ws = load_workbook(io.BytesIO(client.get(f"/models/{model_id}/versions/2").content))["Data"]
    assert ws["J3"].value == 100.5 and ws["J2"].value == "A"
    v1_ws = load_workbook(io.BytesIO(v1.content))["Data"]
    assert isinstance(v1_ws["J3"].value, str)  # version 1 untouched


def test_template_upload_confirm_test_activate(client, demo):
    data, _ = build_builtin(NBFC, date(2026, 9, 30))
    t = client.post(
        "/templates",
        data={"name": "house_nbfc", "sectors": "NBFC"},
        files={"workbook": ("house.xlsx", data, XLSX)},
    ).json()
    assert t["status"] == "draft" and t["mapping"]["rows"]
    assert client.post(f"/templates/{t['id']}/activate").status_code == 409
    mapping = t["mapping"] | {
        "checks": [
            {"sheet": "Checks", "cell_label": "All checks pass", "expect": 1, "tolerance": 0}
        ]
    }
    assert client.post(f"/templates/{t['id']}/mapping", json=mapping).status_code == 200
    test = client.post(f"/templates/{t['id']}/test", json={"symbol": "DEMOFIN"}).json()
    assert test["result"] == "pass", test["issues"]
    assert client.post(f"/templates/{t['id']}/activate").json()["status"] == "active"
    names = {x["name"] for x in client.get("/templates", params={"sector": "NBFC"}).json()}
    assert {"house_nbfc", "nbfc_quarterly"} <= names
    bad = client.post(
        "/templates",
        data={"name": "x", "sectors": "NBFC"},
        files={"workbook": ("x.xlsx", b"not a workbook", XLSX)},
    )
    assert bad.status_code == 422


def test_discover_and_link(client, db, demo):
    found = client.post(
        "/models/discover",
        json={
            "workbooks": [
                {"path": "/Users/k/Models/DEMOFIN_FY27.xlsx"},
                {"path": "/Users/k/Models/notes.xlsx", "text": ["ISIN INE000A01022"]},
                {"path": "/Users/k/Models/budget.xlsx"},
            ]
        },
    ).json()["candidates"]
    assert [(c["symbol"], c["method"]) for c in found] == [
        ("DEMOFIN", "file_name"),
        ("ACMEIND", "contents"),
        (None, "none"),
    ]
    linked = client.post(
        "/models/link",
        json={"symbol": "DEMOFIN", "workbook": {"path": "/Users/k/Models/DEMOFIN_FY27.xlsx"}},
    ).json()
    assert linked["origin"] == "discovered" and linked["doc_tag"]
    again = client.post(
        "/models/discover",
        json={
            "workbooks": [
                {
                    "path": "/elsewhere/renamed.xlsx",
                    "tag_model_id": linked["doc_tag"],
                    "tag_symbol": "DEMOFIN",
                }
            ]
        },
    ).json()["candidates"]
    assert again[0]["method"] == "tag" and again[0]["model_id"] == linked["id"]
    assert db.scalar(select(Filing).where(Filing.company_id == demo.id)) is not None


def test_storage_down_is_a_fast_503(client):
    from analekh.ingest.storage import StorageUnavailable

    def down():
        raise StorageUnavailable("object storage is not reachable at localhost:9000")

    app.dependency_overrides[get_store] = down
    r = client.get("/templates")
    assert r.status_code == 503
    assert "docker compose up -d minio" in r.json()["detail"]


def test_comps_export_shows_each_company_basis(client, db, store):
    solo = Company(nse_symbol="SOLO", name="Solo Systems Limited", isin="INE000S01011")
    db.add(solo)
    db.flush()
    q = pnl(500_000_000, 10_000_000, 400_000_000, 25_000_000)
    ingest_results_xbrl(db, store, solo, build_instance(**Q2, values_q=q, nature="Standalone"))
    ws = load_workbook(io.BytesIO(client.post("/comps", json={"symbols": ["SOLO"]}).content))
    assert ws["Comps"]["B5"].value == "Standalone"
    forced = client.post("/comps", json={"symbols": ["SOLO"], "consolidated": True}).content
    assert load_workbook(io.BytesIO(forced))["Comps"]["B5"].value == "Consolidated"


def test_glance_lines_changes_and_derived_ebitda(client, db, store):
    glow = Company(nse_symbol="GLOW", name="Glow Industries Limited", isin="INE000G01011")
    db.add(glow)
    db.flush()
    crore = 10_000_000

    def quarter(start, end, revenue, pat):
        q = {
            "RevenueFromOperations": revenue * crore,
            "OtherIncome": 5 * crore,
            "Income": (revenue + 5) * crore,
            "Expenses": (revenue - 20) * crore,
            "FinanceCosts": 2 * crore,
            "DepreciationDepletionAndAmortisationExpense": 3 * crore,
            "ProfitBeforeTax": 25 * crore,
            "TaxExpense": (25 - pat) * crore,
            "ProfitLossForPeriod": pat * crore,
        }
        return build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q)

    ingest_results_xbrl(db, store, glow, quarter(date(2025, 7, 1), date(2025, 9, 30), 80, 16))
    ingest_results_xbrl(db, store, glow, quarter(date(2026, 4, 1), date(2026, 6, 30), 90, 18))
    ingest_results_xbrl(db, store, glow, quarter(date(2026, 7, 1), date(2026, 9, 30), 100, 20))
    g = client.get("/companies/GLOW/glance").json()
    assert g["quarter_label"] == "Q2 FY27" and g["previous_end"] == "2026-06-30"
    lines = {line["key"]: line for line in g["lines"]}
    assert float(lines["revenue"]["qoq"]) == 11.1 and float(lines["revenue"]["yoy"]) == 25.0
    # EBITDA = PBT 25 + finance 2 + depreciation 3 - other income 5 = 25 crore
    assert (
        float(lines["ebitda"]["value"]) == 25 * crore and "other income" in lines["ebitda"]["note"]
    )
    assert (
        float(lines["ebitda_margin"]["value"]) == 25.0 and lines["ebitda_margin"]["kind"] == "pct"
    )
    # Margins change in basis points, worked out from unrounded margins: EBITDA margin 25/100 =
    # 25.0% against 25/90 = 27.78% is -278 bps; net margin is 20% in all three quarters.
    assert lines["ebitda_margin"]["qoq"] == "-278" and lines["net_margin"]["qoq"] == "0"
    assert "exceptional_items" not in lines  # not tagged: no row

    # A lender's finance costs are its cost of business: no EBITDA lines for financial sectors.
    glow.sector = "Banking Services"
    db.flush()
    lender = {line["key"] for line in client.get("/companies/GLOW/glance").json()["lines"]}
    assert "ebitda" not in lender and "ebitda_margin" not in lender and "revenue" in lender


def test_glance_for_a_life_insurer_shows_premium_and_ratios(client, db, store):
    life = Company(nse_symbol="LIFEX", name="Lifex Life Insurance Limited", isin="INE000L01011")
    db.add(life)
    db.flush()
    crore = 10_000_000

    def quarter(start, end, net_premium, pat, solvency):
        q = {
            "GrossPremiumIncome": (net_premium + 30) * crore,
            "NetPremiumIncome": net_premium * crore,
            "ProfitLossBeforeTax": (pat + 5) * crore,
            "ProvisionsForTaxes": 5 * crore,
            "ProfitLossAfterTaxAndExtraordinaryItems": pat * crore,
            "SolvencyRatio": solvency,  # tagged as a fraction
            "PersistencyRatio13ThMonth": "0.8077",
            "ExpensesOfManagementRatio": "0.2038",
        }
        return build_instance(
            q_start=start, q_end=end, ytd_start=start, values_q=q, nature="Standalone"
        )

    ingest_results_xbrl(
        db, store, life, quarter(date(2026, 4, 1), date(2026, 6, 30), 2000, 28, "1.9803")
    )
    ingest_results_xbrl(
        db, store, life, quarter(date(2026, 7, 1), date(2026, 9, 30), 2500, 43, "1.8041")
    )
    assert life.results_taxonomy == "life_insurance"  # detected from the premium line items
    g = client.get("/companies/LIFEX/glance").json()
    lines = {line["key"]: line for line in g["lines"]}
    assert list(lines)[:2] == ["gross_premium", "revenue"]
    assert lines["revenue"]["label"] == "Net premium income"
    assert float(lines["revenue"]["qoq"]) == 25.0
    # Ratios read as percentages, and move in bps: 180.41% against 198.03% is -1,762 bps.
    assert (
        float(lines["solvency_ratio"]["value"]) == 180.4
        and lines["solvency_ratio"]["qoq"] == "-1762"
    )
    assert "150%" in lines["solvency_ratio"]["note"]
    assert "ebitda" not in lines and "persistency_61m" not in lines  # not tagged: no row


def test_year_ago_filed_as_a_half_year_explains_the_blank_yoy(client, db, store):
    # Canara Robeco AMC: its first results after listing (Sept 2025) cover April-September only.
    amc = Company(
        nse_symbol="HALFAMC",
        name="Half Year AMC Limited",
        isin="INE000H01011",
        sector="Half-Year AMC Test Sector",  # its own sector: real reporters fill page one
    )
    db.add(amc)
    db.flush()
    crore = 10_000_000
    q = pnl(120 * crore, 0, 60 * crore, 15 * crore)
    for start, end in (
        (date(2025, 4, 1), date(2025, 9, 30)),
        (date(2026, 7, 1), date(2026, 9, 30)),
    ):
        data = build_instance(
            q_start=start, q_end=end, ytd_start=start, values_q=q, nature="Standalone"
        )
        ingest_results_xbrl(db, store, amc, data)

    g = client.get("/companies/HALFAMC/glance").json()
    revenue = next(line for line in g["lines"] if line["key"] == "revenue")
    assert revenue["yoy"] is None
    assert g["year_ago_note"] == (
        "Q2 FY26 wasn't filed as a quarter: the standalone results for 30 Sep 2025 cover "
        "1 Apr 2025 to 30 Sep 2025 only"
    )
    assert g["previous_note"] == "No standalone results for Q1 FY27 on record"

    params = {"quarter_end": "2026-09-30", "sector": "Half-Year AMC Test Sector"}
    d = client.get("/desk", params=params).json()
    row = next(r for r in d["rows"] if r["symbol"] == "HALFAMC")
    assert row["revenue_yoy"] is None and row["yoy_note"] == g["year_ago_note"]


def test_missing_comparison_quarter_says_why(client, db, store):
    # Listed mid-year, first results for the half-year only (Canara Robeco AMC, September 2025):
    # the year-ago quarter was never filed on its own, so YoY is a dash with a reason.
    halfy = Company(
        nse_symbol="HALFY",
        name="Halfy Asset Management Limited",
        isin="INE000H01011",
        sector="Half-Year Test Sector",
    )
    db.add(halfy)
    db.flush()
    for start, end, revenue in (
        (date(2025, 4, 1), date(2025, 9, 30), 2_287_214_000),  # half-year
        (date(2026, 4, 1), date(2026, 6, 30), 1_162_014_000),
        (date(2026, 7, 1), date(2026, 9, 30), 1_215_889_000),
    ):
        q = pnl(revenue, 0, revenue // 2, revenue // 10)
        data = build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q)
        ingest_results_xbrl(db, store, halfy, data)

    g = client.get("/companies/HALFY/glance").json()
    revenue = next(line for line in g["lines"] if line["key"] == "revenue")
    assert revenue["yoy"] is None and revenue["qoq"] is not None
    assert g["previous_note"] is None
    assert g["year_ago_note"].startswith("Q2 FY26 wasn't filed as a quarter")
    assert "1 Apr 2025 to 30 Sep 2025" in g["year_ago_note"]

    params = {"quarter_end": "2026-09-30", "sector": "Half-Year Test Sector"}
    row = client.get("/desk", params=params).json()["rows"]
    mine = next(r for r in row if r["symbol"] == "HALFY")
    assert mine["revenue_yoy"] is None and mine["yoy_note"] == g["year_ago_note"]


def test_results_desk_rows_movers_and_sector_progress(client, db, store):
    from datetime import UTC, datetime

    crore = 10_000_000
    sector = "Desk Test Sector"

    def file_quarter(company, start, end, revenue, pat, filed):
        tax = 5 if pat > 0 else 0
        q = pnl(revenue * crore, 0, (revenue - pat - tax) * crore, tax * crore)
        data = build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q)
        ingest_results_xbrl(db, store, company, data, filed_at=filed)

    companies = {}
    for symbol, isin in (
        ("GROWER", "INE000T01011"),
        ("SLIDER", "INE000T01029"),
        ("TINY", "INE000T01037"),
    ):
        c = Company(nse_symbol=symbol, name=f"{symbol.title()} Ltd", isin=isin, sector=sector)
        db.add(c)
        companies[symbol] = c
    db.flush()
    last_year = (date(2025, 7, 1), date(2025, 9, 30))
    this_year = (date(2026, 7, 1), date(2026, 9, 30))
    for symbol, (rev0, pat0, rev1, pat1, day) in {
        "GROWER": (100, 10, 120, 12, 12),  # +20% revenue, +20% profit
        "SLIDER": (200, 20, 180, -5, 13),  # -10% revenue, turned to a loss
        "TINY": (20, 2, 40, 4, 11),  # under Rs 50 crore this quarter: in the table, not movers
    }.items():
        c = companies[symbol]
        file_quarter(c, *last_year, rev0, pat0, datetime(2025, 10, day, 12, tzinfo=UTC))
        file_quarter(c, *this_year, rev1, pat1, datetime(2026, 10, day, 12, tzinfo=UTC))

    d = client.get("/desk", params={"quarter_end": "2026-09-30", "sector": sector}).json()
    assert d["quarter_label"] == "Q2 FY27" and d["reported"] == 3
    assert [r["symbol"] for r in d["rows"]] == ["SLIDER", "GROWER", "TINY"]  # newest filing first
    grower = next(r for r in d["rows"] if r["symbol"] == "GROWER")
    assert float(grower["revenue_yoy"]) == 20.0 and float(grower["pat_yoy"]) == 20.0
    # Only two companies qualify, so both are "top" and the bottom list stays empty.
    assert [r["symbol"] for r in d["revenue_top"]] == ["GROWER", "SLIDER"]
    assert d["revenue_bottom"] == []
    assert [r["symbol"] for r in d["turned_loss"]] == ["SLIDER"]
    assert all(r["symbol"] != "TINY" for r in d["revenue_top"] + d["revenue_bottom"])
    (progress,) = d["sectors"]
    assert progress["reported"] == 3 and progress["total"] == 3
