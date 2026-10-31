import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { YoyCell } from "./ResultCells";

afterEach(cleanup);

function renderCell(props: Parameters<typeof YoyCell>[0]) {
  render(
    <table>
      <tbody>
        <tr>
          <YoyCell {...props} />
        </tr>
      </tbody>
    </table>,
  );
}

test("shows the change on the previous quarter under the year-on-year figure", () => {
  renderCell({ value: "36.2", of: "revenue", missing: "–", qoq: "4.1" });
  const cell = screen.getByText("+4.1% QoQ").closest("td")!;
  expect(cell.textContent).toContain("+36.2%");
  expect(cell.textContent).toContain("+4.1% QoQ");
  expect(screen.getByText("+4.1% QoQ").className).toContain("delta-up");
});

test("a falling quarter on quarter is marked down", () => {
  renderCell({ value: "10.0", of: "profit", missing: "–", qoq: "-6.3" });
  expect(screen.getByText("-6.3% QoQ").className).toContain("delta-down");
});

test("no previous quarter gives a dash, not zero", () => {
  renderCell({ value: "12.0", of: "revenue", missing: "–", qoq: null });
  const qoq = screen.getByText("– QoQ");
  expect(qoq.className).toContain("muted");
});

test("a table that has no QoQ yet (the watchlist) shows no second line", () => {
  renderCell({ value: "12.0", of: "revenue", missing: "–" });
  expect(screen.queryByText(/QoQ/)).toBeNull();
});

test("year-on-year can be blank while quarter on quarter shows", () => {
  renderCell({ value: null, of: "revenue", missing: <span>no year-ago quarter</span>, qoq: "2.0" });
  expect(screen.getByText("no year-ago quarter")).toBeTruthy();
  expect(screen.getByText("+2.0% QoQ")).toBeTruthy();
});
