import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

// Phase 5 task pane (design doc 13.3, 19.2): works on the open workbook directly, reads the
const API = localStorage.getItem("analekh_api") ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "analekh_token";
const readToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
};
const writeToken = (token: string) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
  }
};

class SignedOut extends Error {}

async function get<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 401) throw new SignedOut();
  if (!res.ok) throw new Error(`Analekh answered ${res.status}.`);
  return (await res.json()) as T;
}

type Item = { id: number; kind: string; sheet: string; cell: string; new_value: string | null };

async function readTag(): Promise<{ modelId?: string; symbol?: string }> {
  return Excel.run(async (ctx) => {
    const props = ctx.workbook.properties.custom;
    props.load("items/key,items/value");
    await ctx.sync();
    const get = (k: string) => props.items.find((p) => p.key === k)?.value as string | undefined;
    return { modelId: get("analekh_model_id"), symbol: get("analekh_symbol") };
  });
}

async function select(sheet: string, cell: string) {
  await Excel.run(async (ctx) => {
    ctx.workbook.worksheets.getItem(sheet).getRange(cell).select();
    await ctx.sync();
  });
}

function TokenForm({ onSave }: { onSave: (token: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave(value.trim());
      }}
    >
      <p>Paste a bridge token from Analekh, Settings, Excel bridge tokens.</p>
      <label>
        Bridge token{" "}
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>{" "}
      <button type="submit" disabled={!value.trim()}>
        Save
      </button>
    </form>
  );
}

function TaskPane() {
  const [tag, setTag] = useState<{ modelId?: string; symbol?: string }>({});
  const [token, setToken] = useState(readToken);
  const [csId, setCsId] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    readTag().then(setTag).catch(() => setTag({}));
  }, []);

  const save = (next: string) => {
    writeToken(next);
    setToken(next);
    setError("");
  };

  const load = async () => {
    setError("");
    try {
      const cs = await get<{ items: Item[] }>(`/change-sets/${encodeURIComponent(csId)}`, token);
      setItems(cs.items);
    } catch (err) {
      if (err instanceof SignedOut) {
        save("");
        setError("That token was not accepted. Make a new one in Analekh, Settings.");
      } else {
        setError(err instanceof Error ? err.message : "Analekh could not be reached.");
      }
    }
  };

  if (!token)
    return (
      <main style={{ fontFamily: "Segoe UI, sans-serif", padding: 12 }}>
        <h3>Analekh</h3>
        {error && <p role="alert">{error}</p>}
        <TokenForm onSave={save} />
      </main>
    );

  return (
    <main style={{ fontFamily: "Segoe UI, sans-serif", padding: 12 }}>
      <h3>Analekh</h3>
      <p>{tag.symbol ? `Linked to ${tag.symbol}` : "This workbook is not linked yet."}</p>
      {error && <p role="alert">{error}</p>}
      <input value={csId} onChange={(e) => setCsId(e.target.value)} placeholder="change set id" />
      <button onClick={load} disabled={!csId}>
        Load
      </button>
      <ul>
        {items.map((i) => (
          <li key={i.id} onClick={() => select(i.sheet, i.cell)} style={{ cursor: "pointer" }}>
            {i.kind} {i.sheet}!{i.cell} → {i.new_value ?? ""}
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => save("")}>
        Forget token
      </button>
    </main>
  );
}

Office.onReady(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <TaskPane />
    </StrictMode>,
  );
});
