import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api, errorMessage, type Draft, type ThreadMessage } from "../api/client";
import { ChatPane, type ChatMessage } from "../components/report/ChatPane";
import { DraftPane } from "../components/report/DraftPane";
import { Icon } from "../components/Icon";
import { Badge, ErrorNote, Loading, PageHeader } from "../components/ui";
import { longDate } from "../lib/format";

const TYPE = { quarterly: "Quarterly update", initiating: "Initiating coverage" } as Record<string, string>;
const FORMAT = { word: "Word report", ppt: "PowerPoint" } as Record<string, string>;
const STATUS = { drafting: "Drafting", approved: "Approved", published: "Published" } as Record<string, string>;
const SAVE_AFTER_MS = 1500;

const REASON: Record<string, string> = {
  ungrounded: "a figure could not be sourced",
  rating: "it read like a rating or a target price",
  outside_selection: "it was outside the section you picked",
  bad_unit: "it pointed at a section that does not exist",
  bad_title: "a new section had no title",
  invalid: "the change was not valid",
  "em-dash": "it used an em-dash",
};
const reason = (r: string) => (r.startsWith("lesson:") ? "it broke one of your lessons" : r.startsWith("phrase:") ? `it used "${r.slice(7)}"` : (REASON[r] ?? r));

type Blocked = { unit: number | null; reasons?: string[]; unmatched?: string[]; style?: string[]; lessons?: number[] };

function MessageNote({ m }: { m: ChatMessage }) {
  const meta = (m.meta ?? {}) as { blocked?: Blocked[]; conflicts?: number[]; reply_unmatched?: string[] };
  const blocked = meta.blocked ?? [];
  if (!blocked.length && !meta.conflicts?.length && !meta.reply_unmatched?.length) return null;
  return (
    <ul className="chat-notes">
      {blocked.map((b, i) => (
        <li key={i}>
          {b.unit === null ? "A change" : `Section ${b.unit + 1}`} was not changed: {(b.reasons ?? (b.lessons?.length ? ["lesson:"] : ["ungrounded"])).map(reason).join(", ")}
          {b.unmatched?.length ? ` (${b.unmatched.join(", ")})` : ""}.
        </li>
      ))}
      {!!meta.reply_unmatched?.length && <li>Figures that could not be sourced: {meta.reply_unmatched.join(", ")}.</li>}
      {!!meta.conflicts?.length && (
        <li>
          You asked for something one of your lessons rules out, so your request won. <Link to="/lessons">Review lessons</Link>
        </li>
      )}
    </ul>
  );
}

export function ReportThread() {
  const tid = Number(useParams().id);
  const qc = useQueryClient();
  const thread = useQuery({
    queryKey: ["thread", tid],
    queryFn: () => api.thread(tid),
    enabled: Number.isFinite(tid),
    refetchInterval: (q) => (q.state.data?.busy ? 2000 : false),
  });
  const data = thread.data;
  const [local, setLocal] = useState<Draft | null>(null);
  const localRef = useRef<Draft | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState<File | null>(null);

  useEffect(() => {
    if (!localRef.current) setLocal(null);
  }, [data?.current_version]);
  useEffect(() => () => clearTimeout(timer.current), []);

  if (thread.isPending) return <Loading />;
  if (!data) return <ErrorNote error={thread.error} />;

  const refresh = () => qc.invalidateQueries({ queryKey: ["thread", tid] });
  const draft = local ?? (data.draft as Draft | null);
  const drafting = data.status === "drafting";
  const locked = data.busy || !drafting;
  const messages = data.messages as ThreadMessage[];
  const lastAi = [...messages].reverse().find((m) => m.role === "ai");
  const lastMeta = (lastAi?.meta ?? {}) as { changed_units?: number[]; version_no?: number | null };
  const highlights = lastMeta.version_no === data.current_version ? (lastMeta.changed_units ?? []) : [];
  const canUndo = drafting && !data.busy && !!lastMeta.version_no && lastMeta.version_no === data.current_version && lastMeta.version_no > 1;

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.code === "stale_version") {
      setError("The draft changed since you opened it. Your last edit was not saved; the latest version is shown.");
      localRef.current = null;
      setLocal(null);
    } else setError(errorMessage(e));
    refresh();
  };

  const save = async () => {
    clearTimeout(timer.current);
    const pending = localRef.current;
    if (!pending) return;
    localRef.current = null;
    try {
      await api.saveDraft(tid, data.current_version, pending);
      setError(null);
      await refresh();
      setLocal(null);
    } catch (e) {
      fail(e);
    }
  };

  const onEdit = (next: Draft) => {
    localRef.current = next;
    setLocal(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(save, SAVE_AFTER_MS);
  };

  const send = async (text: string) => {
    await save();
    try {
      await api.sendMessage(tid, text, data.current_version, selected === null ? null : { unit: selected });
      setError(null);
    } catch (e) {
      fail(e);
    }
    refresh();
  };

  const undo = async () => {
    if (!lastMeta.version_no) return;
    try {
      const prev = await api.threadVersion(tid, lastMeta.version_no - 1);
      await api.saveDraft(tid, data.current_version, prev.draft);
    } catch (e) {
      fail(e);
    }
    refresh();
  };

  const approve = async () => {
    await save();
    const n = data.unsourced.length;
    const ask = n ? `${n} figure${n === 1 ? " is" : "s are"} not sourced. Approve anyway? The draft is then frozen and the file is built.` : "Approve the draft? It is then frozen and the file is built.";
    if (!window.confirm(ask)) return;
    try {
      await api.approve(tid, data.current_version);
      setError(null);
    } catch (e) {
      fail(e);
    }
    refresh();
  };

  const publish = async (file: File, confirmed = false) => {
    try {
      await api.publish(tid, file, confirmed);
      setNeedsConfirm(null);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_tag" && !confirmed) {
        setNeedsConfirm(file);
        return;
      }
      fail(e);
    }
    refresh();
  };

  return (
    <div className="page report-thread">
      <PageHeader
        title={`${data.symbol}: ${TYPE[data.report_type] ?? data.report_type}`}
        badges={<Badge tone={drafting ? "warn" : "ok"}>{STATUS[data.status] ?? data.status}</Badge>}
        subtitle={`${data.company_name} · ${FORMAT[data.format] ?? data.format}${data.quarter_end ? ` · quarter ended ${longDate(data.quarter_end)}` : ""}`}
      />
      {error && (
        <p className="thread-error" role="alert">
          {error}
        </p>
      )}
      <div className="thread-actions">
        {drafting && (
          <>
            <button type="button" className="btn-primary" disabled={data.busy || !draft} onClick={approve}>
              <Icon name="check" />
              Approve draft
            </button>
            {canUndo && (
              <button type="button" onClick={undo}>
                Undo the AI's last change
              </button>
            )}
            <span className="muted">{data.busy ? "The AI is writing." : `${data.unsourced.length} figure(s) not sourced.`}</span>
          </>
        )}
        {!drafting && (
          <a className="btn" href={api.threadFileUrl(tid)} download>
            <Icon name="download" />
            Download the {data.format === "word" ? "Word file" : "presentation"}
          </a>
        )}
        {data.status !== "drafting" && (
          <label className="btn">
            <Icon name="upload" />
            {data.status === "published" ? "Publish a corrected file" : "Publish the final file"}
            <input
              type="file"
              className="sr-only"
              aria-label="Final file"
              accept={data.format === "word" ? ".docx,.docm" : ".pptx,.pptm"}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                const f = e.target.files?.[0];
                if (f) publish(f);
                e.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      {needsConfirm && (
        <div className="card confirm-bar" role="alertdialog" aria-label="Confirm the file">
          <p>This file has no Analekh report tag. Is it the final file for this report?</p>
          <button type="button" className="btn-primary" onClick={() => publish(needsConfirm, true)}>
            Yes, publish it
          </button>
          <button type="button" onClick={() => setNeedsConfirm(null)}>
            Cancel
          </button>
        </div>
      )}
      <div className="thread-grid">
        <div>
          {draft ? (
            <DraftPane draft={draft} locked={locked} unsourced={data.unsourced} highlights={highlights} selected={selected} onSelect={setSelected} onEdit={onEdit} onCommit={save} />
          ) : (
            <section className="card">
              <div className="card-body">
                <span className="pulse-bar" aria-hidden="true" />
                <p className="muted">The AI is writing the first draft, section by section.</p>
              </div>
            </section>
          )}
        </div>
        <ChatPane
          messages={messages}
          busy={data.busy}
          onSend={send}
          disabled={!drafting}
          disabledReason="The draft is approved. Edit the file itself from here."
          placeholder={selected === null ? "Ask about the whole draft" : `Ask about section ${selected + 1}`}
          note={(m) => <MessageNote m={m} />}
        />
      </div>
    </div>
  );
}
