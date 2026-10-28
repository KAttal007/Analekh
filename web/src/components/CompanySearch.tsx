import { keepPreviousData, useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type CompanyIndexEntry } from "../api/client";
import { prepareIndex, searchIndex } from "../lib/companySearch";
import { companyIndexQuery, companyQuery, loadCompanyPage } from "../lib/preload";
import { Icon } from "./Icon";

const DEBOUNCE_MS = 120; // server searches only
const PAGE = 20;
const PREFETCH_MS = 150; // pause on a highlighted result before fetching its company page

export type Suggestion = Pick<CompanyIndexEntry, "id" | "nse_symbol" | "name" | "sector">;

// Type-ahead over every NSE company (design doc F2). The list narrows with each keystroke:
export function CompanySearch({
  onPick,
  placeholder = "Search any NSE company by name or ticker",
  label = "Search companies",
  exclude = [],
  shortcut = !onPick,
}: {
  onPick?: (hit: Suggestion) => void;
  placeholder?: string;
  label?: string;
  exclude?: string[];
  shortcut?: boolean;
} = {}) {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [active, setActive] = useState(0);
  const [shown, setShown] = useState(PAGE);
  const listRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = t?.closest("input, textarea, select, [contenteditable='true']");
      if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shortcut]);

  useEffect(() => {
    const t = setTimeout(() => setTerm(q.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [q]);

  const indexQuery = useQuery(companyIndexQuery);
  const index = useMemo(() => (indexQuery.data ? prepareIndex(indexQuery.data) : null), [indexQuery.data]);
  const local = useMemo(() => (index ? searchIndex(index, q) : null), [index, q]);

  const askServer = term.length >= 1 && (local === null || (local.length === 0 && term.length > 2));
  const server = useInfiniteQuery({
    queryKey: ["search", term],
    queryFn: ({ pageParam }) => api.search(term, pageParam, PAGE),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length === PAGE ? pages.length * PAGE : undefined),
    enabled: askServer,
    placeholderData: keepPreviousData, // keep the list on screen while the next one loads
  });

  const fromLocal = local !== null && local.length > 0;
  const skip = new Set(exclude);
  const hits: Suggestion[] = (fromLocal ? local.slice(0, shown) : askServer ? (server.data?.pages.flat() ?? []) : []).filter((h) => !skip.has(h.nse_symbol));
  const current = fromLocal || (term === q.trim() && !server.isPlaceholderData);
  const selected = Math.min(active, hits.length - 1);

  const loadMore = () => {
    if (fromLocal) {
      if (shown < local.length) setShown((n) => n + PAGE);
    } else if (server.hasNextPage && !server.isFetchingNextPage) {
      void server.fetchNextPage();
    }
  };
  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  const highlighted = hits[selected]?.nse_symbol;
  useEffect(() => {
    if (!highlighted || onPick) return;
    const t = setTimeout(() => void qc.prefetchQuery(companyQuery(highlighted)), PREFETCH_MS);
    return () => clearTimeout(t);
  }, [highlighted, qc, onPick]);

  const open = (hit: Suggestion) => {
    setQ("");
    setTerm("");
    if (onPick) onPick(hit);
    else navigate(`/companies/${hit.nse_symbol}`);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!hits.length) return;
      const step = e.key === "ArrowDown" ? 1 : -1;
      const next = Math.min(Math.max(selected + step, 0), hits.length - 1);
      setActive(next);
      if (next >= hits.length - 3) loadMore();
    } else if (e.key === "Enter" && current && hits[selected]) {
      open(hits[selected]);
    } else if (e.key === "Escape") {
      setQ("");
    }
  };

  const typed = q.trim();
  return (
    <div className="search">
      <span className="search-icon">
        <Icon name="search" />
      </span>
      <input
        ref={inputRef}
        aria-label={label}
        placeholder={placeholder}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setActive(0);
          setShown(PAGE);
          listRef.current?.scrollTo?.({ top: 0 });
        }}
        onKeyDown={onKeyDown}
        onFocus={onPick ? undefined : () => void loadCompanyPage()}
      />
      {!q && shortcut && <kbd aria-hidden="true">/</kbd>}
      {typed.length >= 1 && hits.length > 0 && (
        <ul
          ref={listRef}
          className="suggestions"
          role="listbox"
          aria-busy={!current || server.isFetchingNextPage}
          onScroll={(e) => {
            const el = e.currentTarget;
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 48) loadMore();
          }}
        >
          {hits.map((h, i) => (
            <li key={h.id} role="option" aria-selected={i === selected} className={i === selected ? "active" : undefined} onMouseEnter={() => setActive(i)} onClick={() => open(h)}>
              <strong>{h.nse_symbol}</strong>
              <span className="name">{highlight(h.name, fromLocal ? typed : term)}</span>
              {h.sector && <span className="muted">{h.sector}</span>}
            </li>
          ))}
          {server.isFetchingNextPage && <li className="muted">Loading more…</li>}
        </ul>
      )}
    </div>
  );
}

function highlight(name: string, term: string): ReactNode {
  const words = term
    .split(/\s+/)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return name;
  const anchor = term.length === 1 ? "^" : "";
  const parts = name.split(new RegExp(`${anchor}(${words.join("|")})`, "gi"));
  return parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : p));
}
