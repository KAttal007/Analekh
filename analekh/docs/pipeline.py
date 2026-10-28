"""Document pipeline orchestration (design doc 9.1): read -> classify -> select -> extract ->
chunk/embed -> validate against XBRL (V10)."""

from dataclasses import dataclass

import anthropic
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError
from sqlalchemy.orm import Session

from analekh.db.models import Company, Document, Filing
from analekh.docs.chunking import chunk_pages
from analekh.docs.classifier import select_pages
from analekh.docs.embeddings import Embedder, store_chunks
from analekh.docs.extract import extract, save_kpis
from analekh.docs.pdf import read_pages
from analekh.docs.sector_kpis import kpis_for
from analekh.genai.client import Claude
from analekh.ingest.pipeline import QueueRun
from analekh.ingest.storage import ObjectStore, StorageUnavailable


@dataclass
class DocResult:
    pages: int
    selected: list[int]
    kpis: int
    chunks: int


def process_document(
    session: Session,
    store: ObjectStore,
    filing: Filing,
    claude: Claude | None,
    embedder: Embedder | None,
) -> DocResult:
    data = store.get(filing.storage_key)
    pages = read_pages(data)
    if not pages:  # opens but holds nothing (a cut-off download): as unreadable as one that won't
        raise ValueError("the PDF has no readable pages")
    company = session.get(Company, filing.company_id)
    if company is None:
        raise LookupError(f"filing {filing.id} points at a missing company")

    doc = Document(filing_id=filing.id, page_count=len(pages))
    session.add(doc)
    session.flush()

    selected = select_pages(pages, filing.kind)
    kpi_count = 0
    wanted = kpis_for(company.results_taxonomy if company.results_taxonomy != "indas" else company.sector)
    if claude is not None and selected and filing.kind != "transcript":
        extraction = extract(claude, data, pages, selected, company.name, wanted)
        kpi_count = save_kpis(session, filing, extraction)
        # PHASE 3: run V10 here - map KPI names to XBRL logical names where they overlap and

    chunks = store_chunks(session, doc, chunk_pages(pages), embedder)
    filing.status = "parsed"
    return DocResult(len(pages), [s.page for s in selected], kpi_count, chunks)


def _passing(exc: BaseException) -> bool:
    """An outage that says nothing about the document (Claude or storage unreachable, busy)."""
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (408, 409, 429) or exc.status_code >= 500
    return isinstance(
        exc,
        anthropic.APIConnectionError | StorageUnavailable | EndpointConnectionError | ConnectTimeoutError,
    )


def process_documents(
    session: Session,
    store: ObjectStore,
    filings: list[Filing],
    claude: Claude | None,
    embedder: Embedder | None,
) -> QueueRun:
    """Each document in its own savepoint. One that fails is marked failed (meta "error" says
    why; the admin page lists them) and the run goes on: the same bytes would fail again. An
    outage stops the run and leaves the rest as they were, for the next run."""
    run = QueueRun()
    for filing in filings:
        try:
            with session.begin_nested():
                process_document(session, store, filing, claude, embedder)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"[:500]
            if _passing(exc):
                run.stopped = reason
                break
            filing.status = "failed"
            filing.meta = {**(filing.meta or {}), "error": reason}
            run.failed += 1
        else:
            run.done += 1
    return run
