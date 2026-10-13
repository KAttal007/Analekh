import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const DEBOUNCE_MS = 120;
const PAGE = 20;

// Type-ahead over every NSE company (design doc F2). The list narrows with each keystroke:
// "T" lists tickers and names starting with T, "TC" anything with TC in the ticker or name.
// More results load as the list is scrolled (or arrowed) to the end.
export function CompanySearch() {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => setTerm(q.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isPlaceholderData, hasNextPage, isFetchingNextPage, fetchNextPage } =
    useInfiniteQuery({
      queryKey: ["search", term],
      queryFn: ({ pageParam }) => api.search(term, pageParam, PAGE),
      initialPageParam: 0,
      getNextPageParam: (last, pages) => (last.length === PAGE ? pages.length * PAGE : undefined),
      enabled: term.length >= 1,
      placeholderData: keepPreviousData, // keep the list on screen while the next one loads
    });
  const hits = data?.pages.flat() ?? [];
  const current = term === q.trim() && !isPlaceholderData; // results match what was typed
  const selected = Math.min(active, hits.length - 1);

  const loadMore = () => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  };
  useEffect(() => {
    listRef.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  const open = (symbol: string) => {
    setQ("");
    setTerm("");
    navigate(`/companies/${symbol}`);
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
      open(hits[selected].nse_symbol);
    } else if (e.key === "Escape") {
      setQ("");
    }
  };

  return (
    <div className="search">
      <input
        aria-label="Search companies"
        placeholder="Search any NSE company by name or ticker"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setActive(0);
          listRef.current?.scrollTo?.({ top: 0 });
        }}
        onKeyDown={onKeyDown}
      />
      {q.trim().length >= 1 && hits.length > 0 && (
        <ul
          ref={listRef}
          className="suggestions"
          role="listbox"
          aria-busy={!current || isFetchingNextPage}
          onScroll={(e) => {
            const el = e.currentTarget;
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 48) loadMore();
          }}
        >
          {hits.map((h, i) => (
            <li
              key={h.id}
              role="option"
              aria-selected={i === selected}
              className={i === selected ? "active" : undefined}
              onMouseEnter={() => setActive(i)}
              onClick={() => open(h.nse_symbol)}
            >
              <strong>{h.nse_symbol}</strong> {highlight(h.name, term)}
              {h.sector && <span className="muted"> · {h.sector}</span>}
            </li>
          ))}
          {isFetchingNextPage && <li className="muted">Loading more…</li>}
        </ul>
      )}
    </div>
  );
}

// Marks where the typed text (or each typed word) appears in `name`; one letter only at the start.
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
