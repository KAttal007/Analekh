import ReactECharts from "echarts-for-react";
import type { Draft, DraftBlock, DraftUnit } from "../../api/client";

const LABEL = { rating: "Rating", target: "Target price", guidance: "Guidance" } as const;

/** Numbers from `unsourced` that appear in `text`, for the "not sourced" marker. */
export function unsourcedIn(text: string, unsourced: string[]): string[] {
  return unsourced.filter((n) => text.includes(n));
}

function NotSourced({ text, unsourced }: { text: string; unsourced: string[] }) {
  const hits = unsourcedIn(text, unsourced);
  if (!hits.length) return null;
  return (
    <p className="draft-unsourced" role="note">
      Not sourced: {hits.join(", ")}
    </p>
  );
}

function ChartView({ block }: { block: Extract<DraftBlock, { type: "chart" }> }) {
  const option = {
    title: { text: block.title, left: 0, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 12, top: 36, bottom: 24 },
    xAxis: { type: "category", data: block.labels },
    yAxis: { type: "value" },
    series: block.series.map((s) => ({ name: s.name, type: block.chart_type, data: s.values.map(Number) })),
  };
  return (
    <figure className="draft-chart" aria-label={`Chart: ${block.title}`}>
      <ReactECharts option={option} style={{ height: 220 }} notMerge />
      <figcaption className="muted">Ask the AI to change this chart.</figcaption>
    </figure>
  );
}

function rows(text: string): number {
  return Math.min(12, Math.max(2, Math.ceil(text.length / 90)));
}

function BlockEditor({ block, locked, unsourced, onChange }: { block: DraftBlock; locked: boolean; unsourced: string[]; onChange: (b: DraftBlock) => void }) {
  switch (block.type) {
    case "heading":
      return <input className="draft-heading" aria-label="Heading" value={block.text} readOnly={locked} onChange={(e) => onChange({ ...block, text: e.target.value })} />;
    case "paragraph":
      return (
        <>
          <textarea className="draft-text" aria-label="Paragraph" value={block.text} readOnly={locked} rows={rows(block.text)} onChange={(e) => onChange({ ...block, text: e.target.value })} />
          <NotSourced text={block.text} unsourced={unsourced} />
        </>
      );
    case "bullets": {
      const text = block.items.join("\n");
      return (
        <>
          <textarea
            className="draft-text draft-bullets"
            aria-label="Bullet points, one per line"
            value={text}
            readOnly={locked}
            rows={Math.max(2, block.items.length)}
            onChange={(e) => onChange({ ...block, items: e.target.value.split("\n") })}
          />
          <NotSourced text={text} unsourced={unsourced} />
        </>
      );
    }
    case "table":
      return (
        <div className="table-wrap draft-table">
          <table>
            <tbody>
              {[block.header, ...block.rows].map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>
                      <input
                        aria-label={i === 0 ? `Column ${j + 1} heading` : `Row ${i}, column ${j + 1}`}
                        value={cell}
                        readOnly={locked}
                        onChange={(e) => {
                          const all = [block.header, ...block.rows].map((r) => [...r]);
                          all[i][j] = e.target.value;
                          onChange({ ...block, header: all[0], rows: all.slice(1) });
                        }}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <NotSourced text={block.rows.flat().join(" ")} unsourced={unsourced} />
        </div>
      );
    case "chart":
      return <ChartView block={block} />;
    case "placeholder":
      return (
        <p className="draft-placeholder">
          <strong>{LABEL[block.kind]}</strong>
          <span className="muted">You add this in the file, after approval. The AI never writes it.</span>
        </p>
      );
  }
}

// The draft in the chat window (design: report chat). The analyst types straight into any part;
// the parent saves after a pause or on leaving a field. While the AI writes everything is read-only.
export function DraftPane({
  draft,
  locked,
  unsourced,
  highlights,
  selected,
  onSelect,
  onEdit,
  onCommit,
}: {
  draft: Draft;
  locked: boolean;
  unsourced: string[];
  highlights: number[];
  selected: number | null;
  onSelect: (unit: number | null) => void;
  onEdit: (next: Draft) => void;
  onCommit: () => void;
}) {
  const setUnit = (i: number, unit: DraftUnit) => onEdit({ ...draft, units: draft.units.map((u, k) => (k === i ? unit : u)) });
  return (
    <div className="draft-pane" aria-busy={locked} onBlur={onCommit}>
      {draft.units.map((unit, i) => (
        <section key={i} className={`card draft-unit${highlights.includes(i) ? " unit-changed" : ""}${selected === i ? " unit-selected" : ""}`} aria-label={unit.title}>
          <div className="card-header">
            <input className="draft-title" aria-label="Section title" value={unit.title} readOnly={locked} onChange={(e) => setUnit(i, { ...unit, title: e.target.value })} />
            <button type="button" className="btn-sm" aria-pressed={selected === i} onClick={() => onSelect(selected === i ? null : i)}>
              {selected === i ? "Asking about this" : "Ask about this"}
            </button>
          </div>
          <div className="card-body draft-blocks">
            {unit.blocks.map((block, j) => (
              <BlockEditor key={j} block={block} locked={locked} unsourced={unsourced} onChange={(b) => setUnit(i, { ...unit, blocks: unit.blocks.map((x, k) => (k === j ? b : x)) })} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
