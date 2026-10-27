"""Backfill history from manually downloaded files (design doc 4.1, 9.4): on demand when a company
is first analysed in depth, and in background for Nifty 500.

Layout: ``IMPORT_DIR/<NSE_SYMBOL>/<anything>.xml|.pdf``. XBRL uses same parser and validation path
as live filings; PDFs stored for document pipeline. Processed oldest first by name so V5/V7/V9
have history to compare: prefix names with period end (``2025-06-30_results.xml``).
"""

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from analekh.ingest.pipeline import classify_announcement, ingest_results_xbrl, store_document
from analekh.ingest.storage import ObjectStore
from analekh.universe.search import get as resolve


@dataclass
class BackfillSummary:
    ingested: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    unknown_symbols: list[str] = field(default_factory=list)


def run_backfill(
    session: Session, store: ObjectStore, import_dir: Path, symbol: str | None = None
) -> BackfillSummary:
    summary = BackfillSummary()
    folders = (
        [import_dir / symbol] if symbol else sorted(p for p in import_dir.iterdir() if p.is_dir())
    )
    for folder in folders:
        company = resolve(session, folder.name)
        if company is None:
            summary.unknown_symbols.append(folder.name)
            continue
        for path in sorted(folder.iterdir()):
            suffix = path.suffix.lower()
            if suffix == ".xml":
                result = ingest_results_xbrl(
                    session, store, company, path.read_bytes(), source_url=f"import:{path.name}"
                )
                (summary.skipped if result.skipped else summary.ingested).append(str(path))
            elif suffix == ".pdf":
                store_document(
                    session,
                    store,
                    company,
                    path.read_bytes(),
                    kind=classify_announcement(path.stem.replace("_", " ")),
                    source_url=f"import:{path.name}",
                )
                summary.ingested.append(str(path))
    return summary
