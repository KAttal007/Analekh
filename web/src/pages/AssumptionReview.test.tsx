import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import { AssumptionReview } from "./AssumptionReview";
import { ADMIN, ANALYST, type Handler, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const at1042 = () => {
  const d = new Date();
  d.setHours(10, 42, 0, 0);
  return d.toISOString();
};
const HELD = {
  model_id: 1,
  holder_id: "u2",
  holder_name: "Kaushal",
  activity: "update",
  taken_at: at1042(),
  mine: false,
};
const ROW = {
  id: 5,
  driver: "Revenue growth",
  proposed_value: "12%",
  rationale: "Trend",
  decision: "pending",
  final_value: null,
};

function routes(lock: Handler, me = ANALYST, extra: Record<string, Handler> = {}) {
  return {
    "GET /api/auth/me": () => ({ status: 200, body: me }),
    "GET /api/models/1/assumptions": () => ({ status: 200, body: [ROW] }),
    "GET /api/settings/upload-limit": () => ({
      status: 200,
      body: { bytes: 1, ceiling_bytes: 2, min_bytes: 1, lock_poll_seconds: 20 },
    }),
    "GET /api/models/1/lock": lock,
    ...extra,
  };
}
const show = () =>
  renderAt(
    <Routes>
      <Route path="/models/:id/assumptions" element={<AssumptionReview />} />
    </Routes>,
    "/models/1/assumptions",
  );
const disabled = (name: string) =>
  (screen.getByRole("button", { name }) as HTMLButtonElement).disabled;

it("held by a colleague: banner, and the build steps are off", async () => {
  mockApi(routes(() => ({ status: 200, body: HELD })));
  show();
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  expect(disabled("Accept all")).toBe(true);
  expect(disabled("Accept")).toBe(true);
});

it("free: the build steps are on", async () => {
  mockApi(routes(() => ({ status: 200, body: null })));
  show();
  await screen.findByText("Revenue growth");
  expect(disabled("Accept all")).toBe(false);
  expect(screen.queryByText(/In use by/)).toBeNull();
});

it("an admin sees Release lock instead of the build steps", async () => {
  mockApi(routes(() => ({ status: 200, body: HELD }), ADMIN));
  show();
  await screen.findByText("In use by Kaushal since 10:42");
  expect(screen.getByRole("button", { name: "Release lock" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Accept all" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Build model" })).toBeNull();
});

it("a 423 on Accept shows the holder instead of an error", async () => {
  let held = false;
  mockApi(
    routes(() => ({ status: 200, body: held ? HELD : null }), ANALYST, {
      "POST /api/models/1/assumptions/decisions": () => {
        held = true; // the server now reports the colleague's lock too
        return {
          status: 423,
          body: {
            detail: {
              code: "model_locked",
              holder_name: "Kaushal",
              taken_at: at1042(),
              activity: "update",
            },
          },
        };
      },
    }),
  );
  show();
  await screen.findByText("Revenue growth");
  fireEvent.click(screen.getByRole("button", { name: "Accept all" }));
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("when the colleague is done, the rows reload before the buttons come back", async () => {
  let held = true;
  let row: Record<string, unknown> = ROW;
  mockApi(
    routes(() => ({ status: 200, body: held ? HELD : null }), ANALYST, {
      "GET /api/settings/upload-limit": () => ({
        status: 200,
        body: { bytes: 1, ceiling_bytes: 2, min_bytes: 1, lock_poll_seconds: 0.05 },
      }),
      "GET /api/models/1/assumptions": () => ({ status: 200, body: [row] }),
    }),
  );
  show();
  await screen.findByText("In use by Kaushal since 10:42");
  // The colleague edited the row and built; then the model frees.
  row = { ...ROW, decision: "edited", final_value: "10%" };
  held = false;
  await waitFor(() => expect(screen.queryByText(/In use by/)).toBeNull());
  await waitFor(() => expect(screen.getByText("10%")).toBeTruthy());
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
});

it("a 409 on a decision reloads the rows and still shows the error", async () => {
  let gets = 0;
  let row: Record<string, unknown> = ROW;
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/models/1/assumptions": () => {
        gets += 1;
        return { status: 200, body: [row] };
      },
      "POST /api/models/1/assumptions/decisions": () => {
        row = { ...ROW, decision: "edited", final_value: "10%" }; // a colleague decided it
        return { status: 409, body: { detail: "assumption 5 is already decided" } };
      },
    }),
  );
  show();
  await screen.findByText("Revenue growth");
  await waitFor(() => expect(disabled("Accept")).toBe(false));
  const before = gets;
  fireEvent.click(screen.getByRole("button", { name: "Accept" }));
  await waitFor(() => expect(gets).toBeGreaterThan(before));
  expect(await screen.findByText("10%")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("already decided");
});
