import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage, type Lesson } from "../api/client";
import { Badge, EmptyState, Loading, PageHeader } from "../components/ui";
import { useMe } from "../lib/auth";

const KIND = { phrase: "Wording", structure: "Structure", judged: "Style" } as Record<string, string>;

function LessonRow({ lesson, admin, onChanged }: { lesson: Lesson; admin: boolean; onChanged: () => void }) {
  const [text, setText] = useState(lesson.text);
  const [error, setError] = useState<string | null>(null);
  const editable = lesson.mine || (lesson.scope === "firm" && admin);
  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setError(null);
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  return (
    <li className="lesson-row">
      <div className="lesson-text">
        {editable ? (
          <input aria-label="Lesson" value={text} maxLength={300} onChange={(e) => setText(e.target.value)} />
        ) : (
          <span>{lesson.text}</span>
        )}
        <span className="lesson-tags">
          <Badge>{KIND[lesson.test_kind] ?? lesson.test_kind}</Badge>
          {lesson.scope === "firm" && <Badge tone="accent">Firm</Badge>}
          {lesson.strength > 1 && <span className="muted">learnt {lesson.strength} times</span>}
          {lesson.source_thread_id && <Link to={`/reports/${lesson.source_thread_id}`}>From this report</Link>}
        </span>
        {error && (
          <span className="thread-error" role="alert">
            {error}
          </span>
        )}
      </div>
      {editable && (
        <span className="lesson-actions">
          {text !== lesson.text && (
            <button type="button" className="btn-sm btn-primary" onClick={() => run(() => api.editLesson(lesson.id, { text }))}>
              Save
            </button>
          )}
          <button type="button" className="btn-sm" onClick={() => run(() => api.editLesson(lesson.id, { status: lesson.status === "active" ? "retired" : "active" }))}>
            {lesson.status === "active" ? "Retire" : "Bring back"}
          </button>
          {lesson.mine && (
            <button type="button" className="btn-sm" onClick={() => window.confirm("Delete this lesson? The AI forgets it.") && run(() => api.deleteLesson(lesson.id))}>
              Delete
            </button>
          )}
        </span>
      )}
      {admin && lesson.scope === "analyst" && (
        <button type="button" className="btn-sm" onClick={() => run(() => api.promoteLesson(lesson.id))}>
          Make it a firm lesson
        </button>
      )}
    </li>
  );
}

// What the AI has learnt from published reports (design: lessons). Every model reads the active
// lessons and is tested against them before it replaces the current one.
export function Lessons() {
  const qc = useQueryClient();
  const me = useMe();
  const lessons = useQuery({ queryKey: ["lessons"], queryFn: api.lessons });
  if (lessons.isPending) return <Loading />;
  const all = lessons.data ?? [];
  const admin = me.data?.role === "admin";
  const refresh = () => qc.invalidateQueries({ queryKey: ["lessons"] });
  const group = (status: string) => all.filter((l) => l.status === status);
  return (
    <div className="page">
      <PageHeader title="Lessons" subtitle="What the AI has learnt from your published reports. Edit any of them, or retire one the AI should stop following." />
      {all.length === 0 ? (
        <EmptyState icon="star" title="No lessons yet">
          Lessons are drawn from each report you publish: how you changed the AI's draft, and the file you sent out.
        </EmptyState>
      ) : (
        ["active", "retired"].map((status) =>
          group(status).length ? (
            <section key={status} className="card" aria-label={status === "active" ? "Active" : "Retired"}>
              <div className="card-header">
                <h2>{status === "active" ? "Active" : "Retired"}</h2>
                <span className="muted">{group(status).length}</span>
              </div>
              <ul className="lesson-list">
                {group(status).map((l) => (
                  <LessonRow key={`${l.id}-${l.updated_at}`} lesson={l} admin={admin} onChanged={refresh} />
                ))}
              </ul>
            </section>
          ) : null,
        )
      )}
    </div>
  );
}
