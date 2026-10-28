import type { ReactNode } from "react";
import { changeTitle, crore, money, signedPct, tone, type Scale } from "../lib/format";

const TOP_LINE_TAG: Record<string, { tag: string; title: string }> = {
  banking: { tag: "int.", title: "Interest earned" },
  insurance: { tag: "prem.", title: "Premium earned" },
  life_insurance: { tag: "prem.", title: "Net premium income" },
};

export function ResultColumns() {
  return (
    <>
      <th className="num d-mcap" title="At the latest close loaded from NSE's bhavcopy">
        Market cap
      </th>
      <th className="num">Revenue</th>
      <th className="num" title="Latest quarter on the same quarter a year earlier">
        YoY
      </th>
      <th className="num">Net profit</th>
      <th className="num" title="Latest quarter on the same quarter a year earlier">
        YoY
      </th>
    </>
  );
}

export function BasisHeader() {
  return (
    <th className="d-basis" title="C = consolidated, S = standalone">
      Basis
    </th>
  );
}

export function MarketCapCell({ value, title, missing }: { value: string | null | undefined; title?: string; missing: ReactNode }) {
  return (
    <td className="num d-mcap" data-label="Mkt cap" title={title}>
      {value == null ? missing : crore(value)}
    </td>
  );
}

export function RevenueCell({ value, taxonomy, scale }: { value: string | null | undefined; taxonomy: string; scale: Scale }) {
  const tag = TOP_LINE_TAG[taxonomy];
  return (
    <td className="num d-rev" data-label="Revenue">
      {money(value, scale)}
      {tag && (
        <span className="desk-tag" title={tag.title}>
          {tag.tag}
        </span>
      )}
    </td>
  );
}

export function ProfitCell({ value, scale }: { value: string | null | undefined; scale: Scale }) {
  return (
    <td className="num d-pat" data-label="Net profit">
      {money(value, scale)}
    </td>
  );
}

export function YoyCell({ value, of, missing }: { value: string | null | undefined; of: "revenue" | "profit"; missing: ReactNode }) {
  return (
    <td className={`num ${of === "revenue" ? "d-revy" : "d-paty"} ${tone(value)}`} title={changeTitle(value, "pct")}>
      {value == null ? missing : signedPct(value)}
    </td>
  );
}

export function BasisCell({ consolidated }: { consolidated: boolean | null | undefined }) {
  return (
    <td className="d-basis">
      {consolidated != null && (
        <span className="desk-basis" title={consolidated ? "Consolidated" : "Standalone"}>
          {consolidated ? "C" : "S"}
        </span>
      )}
    </td>
  );
}
