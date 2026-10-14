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
