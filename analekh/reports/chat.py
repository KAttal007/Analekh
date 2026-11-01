"""One chat turn: the analyst asks, the AI may change the draft (design: the flow).

The model answers with a closed JSON object: a reply for the chat and a list of unit changes. Each
change is checked on its own: numbers against this turn's tool results (rule 3), the style filter,
and a scan for rating or target wording (rule 8, the AI never writes one). A change that fails is not
inserted; it is returned blocked with the reason. Placeholders are never touched, and the analyst
decides about charts. Accepted changes are saved as one `ai_reply` version.
"""

import gzip
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import ReportThread, ThreadMessage
from analekh.genai.grounding import check
from analekh.genai.reports import SYSTEM, run_report
from analekh.genai.tools import to_json as tool_json
from analekh.ingest.storage import ObjectStore, unpack
from analekh.reports.draft import Block, Chart, Draft, DraftError, Placeholder, Unit, parse_draft, to_json
from analekh.reports.lessons import Rule, has_phrase, run_lesson_test
from analekh.reports.mask import mask_text
from analekh.reports.sections import markdown_to_blocks, style_problems, unit_to_markdown
from analekh.reports.store import load_draft, save_version

_TURN_RULES = (
    "\n5. You are in a chat with the analyst about a draft report. Reply with ONE JSON object and "
    'nothing else: {"reply": "<short note to the analyst>", "changes": [{"unit": <index>, '
    '"title": "<only for a new section>", "markdown": "<new body of that section>", '
    '"keep_charts": true}]}. Use "changes": [] when the analyst only asks a question. '
    "A change replaces the whole body of that section, so include everything the section should keep. "
    "To add a section use the next free index and a title. Charts already in a section are kept "
    'unless "keep_charts" is false; a new chart goes in "charts" with its series sources. '
    "6. Never write a rating, recommendation or target price; the analyst adds those. "
    "7. No em-dashes, no stock phrases."
)


@dataclass(frozen=True)
class Selection:
    unit: int
    block: int | None = None


class _Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Any = Field(...)
    title: StrictStr | None = None
    markdown: StrictStr
    keep_charts: StrictBool = True
    charts: list[Chart] = []


class _Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: StrictStr
    changes: list[_Change] = []


@dataclass
class BlockedChange:
    unit: int | None
    reasons: list[str]
    unmatched: list[str] = field(default_factory=list)


@dataclass
class TurnResult:
    reply: str
    reply_blocked: bool
    reply_unmatched: list[str]
    changed_units: list[int]
    version_no: int | None
    blocked: list[BlockedChange]
    tool_calls: list[dict[str, Any]]
    results: list[Any]
    conflicts: list[int] = field(default_factory=list)  # lessons the analyst explicitly overrode


def _parse_turn(text: str) -> _Turn | None:
    body = text.strip()
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body)
    try:
        return _Turn.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        return None


def _chart_text(blocks: list[Chart]) -> str:
    return " ".join(" ".join([c.title, *c.labels, *(s.name for s in c.series), *(v for s in c.series for v in s.values)]) for c in blocks)


def _build_unit(old: Unit | None, change: _Change, results: list[Any]) -> tuple[Unit | None, list[str], list[str]]:
    """The unit after `change`, or None with the reasons it was refused and its unmatched numbers."""
    title = change.title if change.title is not None else (old.title if old else None)
    if not title:
        return None, ["bad_title"], []
    text = f"{title}\n{change.markdown}\n{_chart_text(change.charts)}"
    reasons: list[str] = []
    unmatched = check(text, results).unmatched
    if unmatched:
        reasons.append("ungrounded")
    reasons += style_problems(text)
    if mask_text(text).hits:
        reasons.append("rating")
    if reasons:
        return None, reasons, unmatched
    kept: list[Block] = []
    if old:
        kept = [b for b in old.blocks if isinstance(b, Chart) and change.keep_charts and not change.charts]
    placeholders = [b for b in (old.blocks if old else []) if isinstance(b, Placeholder)]
    return Unit(title=title, blocks=[*markdown_to_blocks(change.markdown), *change.charts, *kept, *placeholders]), [], []


def _history(db: Session, thread: ReportThread) -> str:
    rows = list(db.scalars(select(ThreadMessage).where(ThreadMessage.thread_id == thread.id).order_by(ThreadMessage.id.desc()).limit(get_settings().chat_history_messages)))
    return "\n".join(f"{'Analyst' if m.role == 'analyst' else 'You'}: {m.body}" for m in reversed(rows))


def _rules(lessons: Sequence[Rule | str]) -> list[Rule]:
    """Lessons as rules; plain strings (tests, older callers) become text-only rules with no test."""
    return [x if isinstance(x, Rule) else Rule(0, x, "judged", {}) for x in lessons]


def _prompt(draft: Draft, history: str, message: str, selection: Selection | None, rules: list[Rule], feedback: str | None = None) -> str:
    parts = ["The draft as it stands:"]
    for i, u in enumerate(draft.units):
        parts.append(f"\n[section {i}] {u.title}\n{unit_to_markdown(u)}")
    if rules:
        parts.append("\nThe analyst has taught you these rules; follow them:\n" + "\n".join(f"- {r.text}" for r in rules))
    if history:
        parts.append(f"\nEarlier in this chat:\n{history}")
    if selection:
        where = f"section {selection.unit}" + (f", block {selection.block}" if selection.block is not None else "")
        parts.append(f"\nThe analyst has selected {where}. Change only that section.")
    parts.append(f"\nThe analyst now says:\n{message}")
    if feedback:
        parts.append(f"\n{feedback}")
    return "\n".join(parts)


def _lesson_check(unit: Unit, rules: list[Rule], message: str) -> tuple[list[Rule], list[Rule]]:
    """Rules the unit breaks: (failing, conflicts). A banned word the analyst asked for is a conflict:
    the analyst wins, and the lesson is offered for retiring (design: lessons)."""
    failing: list[Rule] = []
    conflicts: list[Rule] = []
    for rule in rules:
        if rule.kind not in ("phrase", "structure") or run_lesson_test(rule, unit).passed:
            continue
        asked = rule.kind == "phrase" and any(has_phrase(message, w) for w in rule.spec.get("banned", []))
        (conflicts if asked else failing).append(rule)
    return failing, conflicts


@dataclass
class _Outcome:
    units: list[Unit]
    changed: list[int]
    blocked: list[BlockedChange]
    conflicts: list[int]
    broken: list[tuple[int, Rule]]


def _apply(turn: _Turn | None, draft: Draft, results: list[Any], selection: Selection | None, rules: list[Rule], message: str) -> _Outcome:
    out = _Outcome(list(draft.units), [], [], [], [])
    for ch in turn.changes if turn else []:
        idx = ch.unit
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx <= len(out.units):
            out.blocked.append(BlockedChange(None, ["bad_unit"]))
            continue
        if selection is not None and idx != selection.unit:
            out.blocked.append(BlockedChange(idx, ["outside_selection"]))
            continue
        new, reasons, unmatched = _build_unit(out.units[idx] if idx < len(out.units) else None, ch, results)
        if new is None:
            out.blocked.append(BlockedChange(idx, reasons, unmatched))
            continue
        failing, conflicts = _lesson_check(new, rules, message)
        out.conflicts += [r.id for r in conflicts]
        if failing:
            out.broken += [(idx, r) for r in failing]
            continue
        if idx == len(out.units):
            out.units.append(new)
        else:
            out.units[idx] = new
        out.changed.append(idx)
    return out


def run_turn(
    db: Session,
    store: ObjectStore,
    claude: Any,
    executor: Any,
    thread: ReportThread,
    message: str,
    selection: Selection | None = None,
    by_user_id: str | None = None,
    lessons: Sequence[Rule | str] = (),
) -> TurnResult:
    draft = load_draft(db, store, thread)
    parent = thread.current_version
    rules = _rules(lessons)
    history = _history(db, thread)
    db.add(ThreadMessage(thread_id=thread.id, role="analyst", body=message, selection=None if selection is None else {"unit": selection.unit, "block": selection.block}))
    calls: list[dict[str, Any]] = []
    results: list[Any] = []
    exchanges: list[dict[str, Any]] = []
    feedback: str | None = None
    for attempt in range(2):  # one retry when a change breaks a lesson
        prompt = _prompt(draft, history, message, selection, rules, feedback)
        run = run_report(claude, executor, "thread_turn", prompt=prompt, system_text=SYSTEM + _TURN_RULES)
        calls += run.tool_calls
        results += run.results
        exchanges += run.exchanges
        turn = _parse_turn(run.text)
        outcome = _apply(turn, draft, results, selection, rules, message)
        if not outcome.broken or attempt == 1:
            break
        feedback = "Your last answer broke the analyst's rules. Write it again and follow them:\n" + "\n".join(f"- {r.text}" for _, r in outcome.broken)
    outcome.blocked += [BlockedChange(idx, [f"lesson:{r.id}"]) for idx, r in outcome.broken]

    reply = turn.reply if turn else run.text
    reply_check = check(reply, results)
    reply_blocked = bool(reply_check.unmatched or style_problems(reply))

    changed = outcome.changed
    version_no = None
    if changed:
        try:
            candidate = parse_draft(to_json(Draft(schema_version=1, format=draft.format, units=outcome.units)))
        except DraftError:
            outcome.blocked.extend(BlockedChange(i, ["invalid"]) for i in changed)
            changed = []
        else:
            version_no = save_version(db, store, thread, candidate, "ai_reply", parent, by_user_id).version_no

    shown = "" if reply_blocked else reply
    stored = "Reply withheld: it contained numbers that could not be sourced, or broke the style rules." if reply_blocked else reply
    conflicts = sorted(set(outcome.conflicts))
    meta = {
        "changed_units": changed,
        "version_no": version_no,
        "reply_blocked": reply_blocked,
        "reply_unmatched": reply_check.unmatched,
        "blocked": [{"unit": b.unit, "reasons": b.reasons, "unmatched": b.unmatched} for b in outcome.blocked],
        "conflicts": conflicts,
    }
    add_ai_message(db, store, thread, body=stored, meta=meta, model_used=getattr(claude, "model", None), prompt=prompt, tool_calls=calls, results=results, exchanges=exchanges)
    return TurnResult(shown, reply_blocked, reply_check.unmatched, changed, version_no, outcome.blocked, calls, results, conflicts)


def thread_results(db: Session, store: ObjectStore, thread: ReportThread) -> list[Any]:
    """Every tool result fetched during the thread, for the sourced-number check."""
    out: list[Any] = []
    for key in db.scalars(select(ThreadMessage.trace_key).where(ThreadMessage.thread_id == thread.id, ThreadMessage.trace_key.is_not(None))):
        if key is not None:
            out.append(json.loads(unpack(store.get(key)))["results"])
    return out


def add_ai_message(
    db: Session,
    store: ObjectStore,
    thread: ReportThread,
    *,
    body: str,
    meta: dict[str, Any],
    model_used: str | None,
    prompt: str,
    tool_calls: list[dict[str, Any]],
    results: list[Any],
    exchanges: list[dict[str, Any]] | None = None,
) -> ThreadMessage:
    """Save the AI's message and, beside it in object storage, the tool calls and results behind it."""
    ai = ThreadMessage(
        thread_id=thread.id,
        role="ai",
        body=body,
        meta=meta,
        model_used=model_used,
        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
    )
    db.add(ai)
    db.flush()
    trace = json.dumps({"tool_calls": tool_calls, "results": json.loads(tool_json(results)), "exchanges": json.loads(tool_json(exchanges or []))}, default=str).encode()
    ai.trace_key = f"reports/{thread.id}/trace-{ai.id}.json.gz"
    store.put(ai.trace_key, gzip.compress(trace, mtime=0))
    db.flush()
    return ai
