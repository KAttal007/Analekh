"""A ready NBFC Excel template for tests. Test data only: the app ships no templates."""

from datetime import date

from sqlalchemy.orm import Session

from analekh.db.models import Template
from analekh.ingest.storage import ObjectStore, sha256
from analekh.templates.onboarding import XLSX
from analekh.templates_builtin import NBFC
from analekh.templates_builtin import build as build_builtin
from analekh.workbook.reader import load, read_structure


def seed_nbfc_template(db: Session, store: ObjectStore) -> Template:
    data, mapping = build_builtin(NBFC, date(2026, 9, 30))
    key = f"templates/test/nbfc_quarterly/v1-{sha256(data)[:12]}.xlsx"
    store.put(key, data, XLSX)
    tmpl = Template(
        owner="test",
        name="nbfc_quarterly",
        sectors=["NBFC"],
        version=1,
        storage_key=key,
        structure=read_structure(load(data)).to_dict(),
        mapping=mapping.model_dump(),
        driver_cells={d.name: {"sheet": "Drivers", "row_label": d.label, "kind": d.kind} for d in NBFC.drivers},
        check_cells={c.cell_label: {"sheet": c.sheet} for c in mapping.checks},
        status="active",
        is_default=True,
    )
    db.add(tmpl)
    db.flush()
    return tmpl
