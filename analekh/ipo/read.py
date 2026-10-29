"""Read an offer document end to end: text chunks for search, then restated statements.

One failing document never stops the others: its status becomes `failed` with the error recorded.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import IpoChunk, IpoDocument
from analekh.docs.chunking import chunk_pages
from analekh.docs.pdf import read_pages
from analekh.genai.client import Claude
from analekh.ingest.storage import ObjectStore
from analekh.ipo.statements import (
    check_figures,
    extract_figures,
    select_statement_pages,
    store_figures,
)
from analekh.ipo.terms import extract_terms, select_terms_pages


def read_document(session: Session, store: ObjectStore, claude: Claude, document: IpoDocument) -> None:
    try:
        # A savepoint: a failure part-way rolls back this document's chunks and figures only.
        with session.begin_nested():
            data = store.get(document.storage_key)
            pages = read_pages(data)
            document.page_count = len(pages)
            for chunk in chunk_pages(pages):
                session.add(IpoChunk(document_id=document.id, page=chunk.page, ord=chunk.ord, text=chunk.text))
            numbers = select_statement_pages(pages)
            figures = extract_figures(claude, data, numbers)
            check_figures(figures)
            store_figures(session, document, figures)
            terms = extract_terms(claude, data, select_terms_pages(pages))
            document.meta = {**(document.meta or {}), "terms": terms}
    except Exception as exc:  # noqa: BLE001 - recorded on the document, never raised
        document.status = "failed"
        document.meta = {**(document.meta or {}), "error": str(exc)}
        session.flush()


def read_pending(session: Session, store: ObjectStore, claude: Claude, limit: int = 10) -> int:
    """Read up to `limit` documents still `new`, each in its own savepoint. Returns how many were tried."""
    pending = session.scalars(select(IpoDocument).where(IpoDocument.status == "new").order_by(IpoDocument.id).limit(limit)).all()
    for document in pending:
        with session.begin_nested():
            read_document(session, store, claude, document)
    return len(pending)
