"""Template onboarding (design doc 14, 6.3).

Upload -> read structure -> suggested mapping with confidence -> analyst confirms once -> test
build with one real company -> activate. Editing makes a new version; models keep the version they
were built on. Uploading an existing model for another company clears its historical hardcoded
inputs (formulas kept); uncertain cells listed, never deleted.
"""

import io
from dataclasses import dataclass, field
from typing import Any

from openpyxl import Workbook
from sqlalchemy import any_, func, literal, select, update
from sqlalchemy.orm import Session

from analekh.db.models import Template, TemplateTest
from analekh.ingest.storage import ObjectStore, sha256
from analekh.templates.files import EXCEL, FileType, slug
from analekh.workbook.labels import AiResolver
from analekh.workbook.mapping import Mapping
from analekh.workbook.reader import StructureMap, excel_kind, has_macros, load, read_structure

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TemplateError(ValueError):
    pass


@dataclass
class ClearReport:
    cleared: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)


def clear_historical_inputs(wb: Workbook, sm: StructureMap) -> ClearReport:
    """Turn an existing model into a template: clear typed actuals, keep every formula."""
    report = ClearReport()
    if sm.axis is None:
        return report
    ws = wb[sm.axis.sheet]
    actual_cols = [c for c in sm.axis.columns if not sm.axis.is_estimate(c)]
    for row in sm.rows:
        if row.sheet != sm.axis.sheet:
            continue
        cells = [ws.cell(row=row.row, column=c) for c in actual_cols]
        numbers = [c for c in cells if isinstance(c.value, int | float)]
        if not numbers:
            continue
        if row.actual_kind == "input":
            for c in numbers:
                c.value = None
                report.cleared.append(f"{ws.title}!{c.coordinate}")
        else:  # mixed row: typed numbers among formulas, a human should decide
            report.uncertain += [f"{ws.title}!{c.coordinate}" for c in numbers]
    return report


def _save(wb: Workbook) -> bytes:
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _next_version(session: Session, owner: str, name: str) -> int:
    current = session.scalar(select(func.max(Template.version)).where(Template.owner == owner, Template.name == name))
    return (current or 0) + 1


def upload(
    session: Session,
    store: ObjectStore,
    data: bytes,
    *,
    name: str,
    sectors: list[str],
    owner: str,
    from_existing_model: bool = False,
    ai: AiResolver | None = None,
) -> Template:
    """``ai`` (e.g. analekh.genai.labels.label_resolver) places labels synonyms and fuzzy
    matching could not; those rows keep a confidence below 0.85 for the user to confirm."""
    wb = load(data)
    sm = read_structure(wb, ai)
    if sm.axis is None:
        raise TemplateError("no period axis found: historical periods must run across columns with labels in one column (section 14.4)")
    cleared = clear_historical_inputs(wb, sm) if from_existing_model else ClearReport()
    if cleared.cleared:
        data = _save(wb)
        sm = read_structure(wb, ai)
    version = _next_version(session, owner, name)
    suffix, content_type = excel_kind(data)  # a template with macros stays an .xlsm
    key = f"templates/{owner}/{slug(name)}/v{version}-{sha256(data)[:12]}{suffix}"
    store.put(key, data, content_type)
    mapping = sm.suggest_mapping(name, sectors)
    tmpl = Template(
        owner=owner,
        name=name,
        sectors=sectors,
        version=version,
        storage_key=key,
        structure=sm.to_dict() | {"cleared": cleared.cleared, "uncertain": cleared.uncertain},
        mapping=mapping.model_dump(),
        driver_cells={d.name: {"sheet": d.forecast_sheet, "row_label": d.forecast_row_label, "kind": "ratio"} for d in mapping.drivers},
        check_cells={c.cell_label: {"sheet": c.sheet} for c in mapping.checks},
        status="draft",
        kind=EXCEL,
        has_macros=has_macros(data),
    )
    session.add(tmpl)
    session.flush()
    return tmpl


def upload_report_template(
    session: Session,
    store: ObjectStore,
    data: bytes,
    *,
    kind: str,
    suffix: str,
    ftype: FileType,
    name: str,
    sectors: list[str],
    owner: str,
) -> Template:
    """A Word or PowerPoint report template: stored byte for byte, active at once. Nothing in our
    code parses or writes it (the report-writing model does), so there is no mapping or test build."""
    from analekh.templates.files import has_macro_project

    version = _next_version(session, owner, name)
    key = f"templates/{owner}/{slug(name)}/v{version}-{sha256(data)[:12]}{suffix}"
    store.put(key, data, ftype.mime)
    tmpl = Template(
        owner=owner,
        name=name,
        sectors=sectors,
        version=version,
        storage_key=key,
        status="active",
        kind=kind,
        has_macros=has_macro_project(data),
    )
    session.add(tmpl)
    session.flush()
    return tmpl


def set_enabled(session: Session, template: Template, enabled: bool) -> Template:
    """Disable keeps the file and every link to models built from it; enable undoes it."""
    if enabled:
        if template.status == "active":
            return template
        if template.kind != EXCEL:  # nothing to test on a report template
            template.status = "active"
            session.flush()
            return template
        return activate(session, template)
    template.status = "disabled"
    template.is_default = False
    session.flush()
    return template


def confirm_mapping(session: Session, template: Template, mapping: dict[str, Any]) -> Mapping:
    """The analyst's confirmed mapping. Confirming resets status to draft until a new test."""
    m = Mapping.model_validate(mapping)
    template.mapping = m.model_dump()
    template.status = "draft"
    session.flush()
    return m


def activate(session: Session, template: Template, make_default: bool = False) -> Template:
    last = session.scalar(select(TemplateTest).where(TemplateTest.template_id == template.id).order_by(TemplateTest.id.desc()))
    if last is None or last.result != "pass":
        raise TemplateError("a passing test build is required before activation (section 14.3)")
    template.status = "active"
    if make_default:
        session.execute(update(Template).where(Template.id != template.id, Template.sectors.overlap(template.sectors)).values(is_default=False))
        template.is_default = True
    session.flush()
    return template


def default_for(session: Session, sector: str | None) -> Template | None:
    """The sector's default active Excel template."""
    q = select(Template).where(Template.status == "active", Template.kind == EXCEL)
    if sector:
        q = q.where(literal(sector) == any_(Template.sectors))
    rows = list(session.scalars(q.order_by(Template.is_default.desc(), Template.id.desc())))
    return rows[0] if rows else None
