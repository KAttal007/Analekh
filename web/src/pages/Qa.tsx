import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { CompanySearch, type Suggestion } from "../components/CompanySearch";
import { ChatPane, type ChatMessage } from "../components/report/ChatPane";
import { EmptyState, PageHeader } from "../components/ui";

type Cite = { filing_id: number; page: number };

function Sources({ m, symbol }: { m: ChatMessage; symbol: string }) {
  const meta = (m.meta ?? {}) as { citations?: Cite[]; unmatched?: string[]; blocked?: boolean };
  if (meta.blocked && meta.unmatched?.length) return <p className="chat-notes">Figures that could not be sourced: {meta.unmatched.join(", ")}.</p>;
  if (!meta.citations?.length) return null;
  return (
    <p className="chat-notes">
      Sources:{" "}
      {meta.citations.map((c, i) => (
        <span key={i}>
          {i > 0 && ", "}
          <Link to={`/companies/${encodeURIComponent(symbol)}`}>
            filing {c.filing_id}, page {c.page}
          </Link>
        </span>
      ))}
    </p>
  );
}

// Q&A (design doc 19.1): a chat over one company's filings, with page sources. Answers with a
// figure no tool returned are withheld. Q&A never teaches the AI lessons.
export function Qa() {
  const [params, setParams] = useSearchParams();
  const chatId = Number(params.get("chat")) || null;
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["qa-threads"], queryFn: api.qaThreads });
  const chat = useQuery({
    queryKey: ["qa", chatId],
    queryFn: () => api.qaThread(chatId as number),
    enabled: chatId !== null,
    refetchInterval: (q) => (q.state.data?.busy ? 2000 : false),
  });

  const start = async (s: Suggestion) => {
    try {
      const made = await api.startQa(s.nse_symbol);
      await qc.invalidateQueries({ queryKey: ["qa-threads"] });
      setParams({ chat: String(made.id) });
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  const ask = async (question: string) => {
    if (chatId === null) return;
    try {
      await api.ask(chatId, question);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
    qc.invalidateQueries({ queryKey: ["qa", chatId] });
  };

  return (
    <div className="page">
      <PageHeader title="Q&A" subtitle="Ask about a company's filings. Every figure in an answer is sourced, with the page it came from." />
      <div className="qa-grid">
        <aside className="card qa-list" aria-label="Your chats">
          <div className="card-body">
            <CompanySearch onPick={start} label="Company to ask about" placeholder="New chat: search a company" />
          </div>
          <ul className="qa-chats">
            {(list.data ?? []).map((t) => (
              <li key={t.id}>
                <button type="button" className="slide-item" aria-pressed={t.id === chatId} onClick={() => setParams({ chat: String(t.id) })}>
                  <span className="badge-mono">{t.symbol}</span>
                  <span>{t.title || "New chat"}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <div>
          {error && (
            <p className="thread-error" role="alert">
              {error}
            </p>
          )}
          {chat.data ? (
            <ChatPane
              messages={chat.data.messages}
              busy={chat.data.busy}
              onSend={ask}
              placeholder={`Ask about ${chat.data.company_name}`}
              note={(m) => <Sources m={m} symbol={chat.data.symbol} />}
            />
          ) : (
            <EmptyState icon="chat" title="Pick a company to start">
              Your chats are listed on the left. Each one is about one company's filings.
            </EmptyState>
          )}
        </div>
      </div>
    </div>
  );
}
