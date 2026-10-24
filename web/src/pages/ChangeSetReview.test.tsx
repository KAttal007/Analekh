import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ADMIN, ANALYST, type Handler, mockApi, renderAt } from "../test-utils";
import { ChangeSetReview } from "./ChangeSetReview";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Today at 10:42 on the viewer's clock, so the banner reads "10:42" in any time zone.
const at1042 = () => {
  const d = new Date();
  d.setHours(10, 42, 0, 0);
  return d.toISOString();
};
const HELD = {
  model_id: 7,
  holder_id: "u2",
  holder_name: "Kaushal",
  activity: "build",
  taken_at: at1042(),
  mine: false,
};
const ITEM = {
  id: 5,
  kind: "actual_write",
  sheet: "Data",
  cell: "J3",
  old_value: null,
  new_value: "975",
  formula_before: null,
  formula_after: null,
  rationale: "Revenue for the quarter",
  source_fact_id: null,
  decision: "pending",
  final_value: null,
};
const CS = {
  id: 3,
  model_id: 7,
  base_version: 1,
  filing_id: 9,
  status: "proposed",
  summary: {},
  items: [ITEM],
};
const LOCKED = {
  status: 423,
  body: {
    detail: { code: "model_locked", holder_name: "Kaushal", taken_at: at1042(), activity: "build" },
  },
};

function routes(lock: Handler, me = ANALYST, extra: Record<string, Handler> = {}) {
  return {
    "GET /api/auth/me": () => ({ status: 200, body: me }),
    "GET /api/change-sets/3": () => ({ status: 200, body: CS }),
    "GET /api/settings/upload-limit": () => ({
      status: 200,
      body: { bytes: 1, ceiling_bytes: 2, min_bytes: 1, lock_poll_seconds: 20 },
    }),
    "GET /api/models/7/lock": lock,
    ...extra,
  };
}
const show = () =>
  renderAt(
    <Routes>
      <Route path="/change-sets/:id" element={<ChangeSetReview />} />
    </Routes>,
    "/change-sets/3",
  );
const disabled = (name: string | RegExp) =>
  (screen.getByRole("button", { name }) as HTMLButtonElement).disabled;

it("held by a colleague: banner, and every decision and Apply are off", async () => {
  mockApi(routes(() => ({ status: 200, body: HELD })));
  show();
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  expect(disabled("Accept")).toBe(true);
  expect(disabled("Skip")).toBe(true);
  expect(disabled(/Accept all actual write/)).toBe(true);
  expect(disabled("Apply approved changes")).toBe(true);
});

it("free: decisions are on, no banner", async () => {
  mockApi(routes(() => ({ status: 200, body: null })));
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Accept")).toBe(false));
  expect(disabled("Skip")).toBe(false);
  expect(screen.queryByText(/In use by/)).toBeNull();
});

it("an admin sees Release lock instead of the decisions", async () => {
  mockApi(routes(() => ({ status: 200, body: HELD }), ADMIN));
  show();
  await screen.findByText("In use by Kaushal since 10:42");
  expect(screen.getByRole("button", { name: "Release lock" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Apply approved changes" })).toBeNull();
});

it("a 423 on a decision shows the holder instead of an error", async () => {
  let held = false;
  mockApi(
    routes(() => ({ status: 200, body: held ? HELD : null }), ANALYST, {
      "POST /api/change-sets/3/decisions": () => {
        held = true;
        return LOCKED;
      },
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Accept")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Accept" }));
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("a 423 on Apply shows the holder instead of an error", async () => {
  let held = false;
  mockApi(
    routes(() => ({ status: 200, body: held ? HELD : null }), ANALYST, {
      "GET /api/change-sets/3": () => ({
        status: 200,
        body: { ...CS, status: "approved", items: [{ ...ITEM, decision: "accepted" }] },
      }),
      "POST /api/change-sets/3/apply": () => {
        held = true;
        return LOCKED;
      },
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Apply approved changes")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Apply approved changes" }));
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("a stale 409 on Apply says so, keeps Apply off and links back to the models", async () => {
  const STALE = "The model has changed since this change set was drafted. Draft a new update.";
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/change-sets/3": () => ({
        status: 200,
        body: { ...CS, status: "approved", items: [{ ...ITEM, decision: "accepted" }] },
      }),
      "POST /api/change-sets/3/apply": () => ({
        status: 409,
        body: {
          detail: { code: "change_set_stale", message: STALE, base_version: 1, latest_version: 2 },
        },
      }),
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Apply approved changes")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Apply approved changes" }));
  expect(await screen.findByText(STALE)).toBeTruthy();
  expect(screen.queryByText(/change_set_stale/)).toBeNull(); // the message, not the raw reply
  await waitFor(() => expect(disabled("Apply approved changes")).toBe(true));
  const back = screen.getByRole("link", { name: "Back to models" });
  expect(back.getAttribute("href")).toBe("/models");
});

it("a 503 recalc_unavailable on Apply shows the server's message and leaves Apply on", async () => {
  const DOWN =
    "Recalculation is unavailable right now. Try Apply again in a few minutes, or apply from Excel with the Analekh bridge.";
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/change-sets/3": () => ({
        status: 200,
        body: { ...CS, status: "approved", items: [{ ...ITEM, decision: "accepted" }] },
      }),
      "POST /api/change-sets/3/apply": () => ({
        status: 503,
        body: { detail: { code: "recalc_unavailable", message: DOWN } },
      }),
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Apply approved changes")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Apply approved changes" }));
  expect(await screen.findByText(DOWN)).toBeTruthy();
  expect(screen.queryByText(/recalc_unavailable/)).toBeNull(); // the message, not the raw reply
  expect(screen.getAllByRole("alert")).toHaveLength(1); // no second, raw error note
  expect(disabled("Apply approved changes")).toBe(false); // nothing was saved: try again
  expect(screen.queryByRole("link", { name: "Back to models" })).toBeNull();
});

it("a 422 recalc_cannot_compute on Apply shows the server's message and names the cells", async () => {
  const CANNOT =
    "Analekh cannot recalculate 2 cell(s) in this model (Sheet1!E2, Sheet1!E3). They use a function it cannot run, such as a custom VBA function. Apply from Excel with the Analekh bridge instead.";
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/change-sets/3": () => ({
        status: 200,
        body: { ...CS, status: "approved", items: [{ ...ITEM, decision: "accepted" }] },
      }),
      "POST /api/change-sets/3/apply": () => ({
        status: 422,
        body: {
          detail: {
            code: "recalc_cannot_compute",
            message: CANNOT,
            cells: ["Sheet1!E2", "Sheet1!E3"],
            total: 2,
          },
        },
      }),
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Apply approved changes")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Apply approved changes" }));
  expect(await screen.findByText(CANNOT)).toBeTruthy();
  expect(screen.queryByText(/recalc_cannot_compute/)).toBeNull(); // the message, not the raw reply
  expect(screen.getAllByRole("alert")).toHaveLength(1);
});

it("a 409 on a decision reloads the change set and still shows the error", async () => {
  let gets = 0;
  let item: Record<string, unknown> = ITEM;
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/change-sets/3": () => {
        gets += 1;
        return { status: 200, body: { ...CS, items: [item] } };
      },
      "POST /api/change-sets/3/decisions": () => {
        item = { ...ITEM, decision: "edited", final_value: "970" }; // a colleague decided it
        return { status: 409, body: { detail: "item 5 is already decided: reload the change set" } };
      },
    }),
  );
  show();
  await screen.findByText("Revenue for the quarter");
  await waitFor(() => expect(disabled("Accept")).toBe(false));
  const before = gets;
  fireEvent.click(screen.getByRole("button", { name: "Accept" }));
  await waitFor(() => expect(gets).toBeGreaterThan(before));
  expect(await screen.findByText("970")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("already decided");
});
