import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Models } from "./Models";
import { ADMIN, ANALYST, type Handler, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const MODEL = {
  id: 1,
  company_id: 10,
  template_id: null,
  name: "TCS model",
  origin: "linked",
  doc_tag: "5f0c6b8e-0000-4000-8000-000000000001",
  file_path: "C:/models/TCS.xlsx",
  last_seen: null,
};
const SETTINGS = {
  bytes: 1,
  ceiling_bytes: 2,
  min_bytes: 1,
  updated_by: null,
  updated_at: null,
  lock_poll_seconds: 20,
};
// Today at 10:42 on the viewer's clock, so the banner reads "10:42" in any time zone.
const at1042 = () => {
  const d = new Date();
  d.setHours(10, 42, 0, 0);
  return d.toISOString();
};
const lockOf = (over: Record<string, unknown> = {}) => ({
  model_id: 1,
  holder_id: "u2",
  holder_name: "Kaushal",
  activity: "update",
  taken_at: at1042(),
  mine: false,
  ...over,
});

function routes(lock: Handler, me = ANALYST, extra: Record<string, Handler> = {}) {
  return {
    "GET /api/auth/me": () => ({ status: 200, body: me }),
    "GET /api/models": () => ({ status: 200, body: [MODEL] }),
    "GET /api/settings/upload-limit": () => ({ status: 200, body: SETTINGS }),
    "GET /api/companies/index": () => ({
      status: 200,
      body: [{ id: 10, nse_symbol: "TCS", name: "TCS", isin: null, sector: null }],
    }),
    "GET /api/models/1/lock": lock,
    ...extra,
  };
}
const mockLock = (over: Record<string, unknown> | null, me = ANALYST) =>
  mockApi(routes(() => ({ status: 200, body: over === null ? null : lockOf(over) }), me));

const disabled = (name: RegExp) =>
  (screen.getByRole("button", { name }) as HTMLButtonElement).disabled;

it("disables update, build and report when another person holds the lock", async () => {
  mockLock({ holder_name: "Kaushal", mine: false });
  renderAt(<Models />);
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  expect(disabled(/update/i)).toBe(true);
  expect(disabled(/build/i)).toBe(true);
  expect(disabled(/report/i)).toBe(true);
  expect(screen.queryByRole("button", { name: "Release lock" })).toBeNull();
});

it("a free model: actions enabled, no banner", async () => {
  const calls = mockLock(null);
  renderAt(<Models />);
  await screen.findByText("TCS model");
  await waitFor(() => expect(calls.some((c) => c.url === "/api/models/1/lock")).toBe(true));
  expect(disabled(/update/i)).toBe(false);
  expect(disabled(/build/i)).toBe(false);
  expect(disabled(/report/i)).toBe(false);
  expect(screen.queryByText(/In use by/)).toBeNull();
});

it("my own lock: actions enabled, no banner", async () => {
  const calls = mockLock({ mine: true, holder_name: "Kaushal Attal" });
  renderAt(<Models />);
  await screen.findByText("TCS model");
  await waitFor(() => expect(calls.some((c) => c.url === "/api/models/1/lock")).toBe(true));
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.queryByText(/In use by/)).toBeNull();
  expect(disabled(/update/i)).toBe(false);
});

it("an admin sees the banner and Release lock, not the actions", async () => {
  let held = true;
  const calls = mockApi(
    routes(() => ({ status: 200, body: held ? lockOf() : null }), ADMIN, {
      "POST /api/admin/locks/1/release": () => {
        held = false;
        return { status: 204 };
      },
    }),
  );
  renderAt(<Models />);
  await screen.findByText("In use by Kaushal since 10:42");
  expect(screen.queryByRole("button", { name: /update/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /build/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /report/i })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Release lock" }));
  await waitFor(() => expect(screen.queryByText(/In use by/)).toBeNull());
  const release = calls.findIndex((c) => c.url === "/api/admin/locks/1/release");
  expect(release).toBeGreaterThan(-1);
  expect(calls[release].method).toBe("POST");
  // The lock is asked for again after the release, and the actions come back.
  expect(calls.slice(release + 1).some((c) => c.url === "/api/models/1/lock")).toBe(true);
  expect(disabled(/update/i)).toBe(false);
});

it("a 423 on Update shows who holds the model and checks the lock again", async () => {
  let lockAsks = 0;
  mockApi(
    routes(
      () => {
        lockAsks += 1;
        return { status: 200, body: lockAsks === 1 ? null : lockOf({ activity: "report" }) };
      },
      ANALYST,
      {
        "GET /api/companies/TCS/filings": () => ({
          status: 200,
          body: [
            { id: 7, kind: "results_xbrl", period_end: "2026-06-30", meta: {}, status: "parsed" },
            { id: 9, kind: "results_xbrl", period_end: "2026-09-30", meta: {}, status: "parsed" },
          ],
        }),
        "POST /api/models/1/sync": () => ({
          status: 423,
          body: {
            detail: {
              code: "model_locked",
              holder_name: "Kaushal",
              taken_at: at1042(),
              activity: "report",
            },
          },
        }),
      },
    ),
  );
  renderAt(<Models />);
  await screen.findByText("TCS model");
  await waitFor(() => expect(lockAsks).toBe(1));
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  await waitFor(() => expect(lockAsks).toBe(2));
  expect(disabled(/update/i)).toBe(true);
  expect(screen.queryByRole("alert")).toBeNull(); // no generic error as well
});

it("Update queues a sync on the newest filing", async () => {
  const calls = mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/companies/TCS/filings": () => ({
        status: 200,
        body: [
          { id: 7, kind: "results_xbrl", period_end: "2026-06-30", meta: {}, status: "parsed" },
          { id: 9, kind: "results_xbrl", period_end: "2026-09-30", meta: {}, status: "parsed" },
        ],
      }),
      "POST /api/models/1/sync": () => ({ status: 200, body: { job_id: "j1", status: "queued" } }),
    }),
  );
  renderAt(<Models />);
  await screen.findByText("TCS model");
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  await waitFor(() =>
    expect(calls.find((c) => c.url === "/api/models/1/sync")?.body).toEqual({ filing_id: 9 }),
  );
});

it("Update refuses when the newest results are blocked, and drafts nothing", async () => {
  const calls = mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/companies/TCS/filings": () => ({
        status: 200,
        body: [
          { id: 7, kind: "results_xbrl", period_end: "2026-06-30", meta: {}, status: "parsed" },
          {
            id: 9,
            kind: "results_xbrl",
            period_end: "2026-09-30",
            meta: { blocks_auto_apply: true },
            status: "parsed",
          },
        ],
      }),
      "POST /api/models/1/sync": () => ({ status: 200, body: { job_id: "j1", status: "queued" } }),
    }),
  );
  renderAt(<Models />);
  await screen.findByText("TCS model");
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  const dialog = await screen.findByRole("alertdialog");
  expect(dialog.getAttribute("aria-modal")).toBe("true");
  expect(dialog.textContent).toContain("2026-09-30");
  expect(dialog.textContent).toMatch(/newest results.*blocked/i);
  expect(dialog.textContent).toMatch(/nothing was drafted/i);
  expect(dialog.textContent).toMatch(/by hand/i);
  expect(dialog.textContent).not.toContain("—"); // no em-dashes
  const ok = screen.getByRole("button", { name: "OK" });
  await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  expect(screen.queryByRole("alert")).toBeNull(); // the pop-up, not the inline error
  expect(calls.some((c) => c.url === "/api/models/1/sync")).toBe(false);
  expect(calls.some((c) => c.url === "/api/models/1/lock/release")).toBe(false);
  fireEvent.click(ok);
  expect(screen.queryByRole("alertdialog")).toBeNull();
  // Escape closes it too.
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  const again = await screen.findByRole("alertdialog");
  fireEvent.keyDown(again, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(calls.some((c) => c.url === "/api/models/1/sync")).toBe(false);
});

const blockedRoutes = () =>
  routes(() => ({ status: 200, body: null }), ANALYST, {
    "GET /api/companies/TCS/filings": () => ({
      status: 200,
      body: [
        {
          id: 9,
          kind: "results_xbrl",
          period_end: "2026-09-30",
          meta: { blocks_auto_apply: true },
          status: "parsed",
        },
      ],
    }),
  });

/** Press Update the way a browser does: the button takes focus, then loses it to the page body
 *  as it turns disabled while the update is pending, before the pop-up opens. */
async function pressUpdateUntilBlocked(): Promise<{ button: HTMLElement; dialog: HTMLElement }> {
  const button = screen.getByRole("button", { name: /update/i });
  button.focus();
  fireEvent.click(button);
  button.blur(); // jsdom does no focus fixup for a disabled control: do the browser's part
  expect(document.activeElement).toBe(document.body);
  const dialog = await screen.findByRole("alertdialog");
  return { button, dialog };
}

it("closing the blocked pop-up gives focus back to Update", async () => {
  mockApi(blockedRoutes());
  renderAt(<Models />);
  await screen.findByText("TCS model");
  const first = await pressUpdateUntilBlocked();
  await waitFor(() => expect(first.dialog.contains(document.activeElement)).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "OK" }));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(document.activeElement).toBe(first.button);
  const second = await pressUpdateUntilBlocked();
  fireEvent.keyDown(second.dialog, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(document.activeElement).toBe(second.button);
});

it("a click on the pop-up's backdrop keeps focus inside, so Escape still closes it", async () => {
  mockApi(blockedRoutes());
  renderAt(<Models />);
  await screen.findByText("TCS model");
  const { dialog } = await pressUpdateUntilBlocked();
  const ok = screen.getByRole("button", { name: "OK" });
  await waitFor(() => expect(document.activeElement).toBe(ok));
  const backdrop = dialog.parentElement as HTMLElement;
  // A browser moves focus on mousedown unless the default is prevented.
  const moved = fireEvent.mouseDown(backdrop);
  if (moved) (document.activeElement as HTMLElement).blur();
  expect(document.activeElement).toBe(ok);
  fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
});

it("other Update errors stay inline, with no pop-up", async () => {
  mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/companies/TCS/filings": () => ({ status: 200, body: [] }),
    }),
  );
  renderAt(<Models />);
  await screen.findByText("TCS model");
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  const note = await screen.findByRole("alert");
  expect(note.textContent).toContain("No filed results to update from yet.");
  expect(screen.queryByRole("alertdialog")).toBeNull();
});

it("Update reads results filings only", async () => {
  const calls = mockApi(
    routes(() => ({ status: 200, body: null }), ANALYST, {
      "GET /api/companies/TCS/filings": () => ({
        status: 200,
        body: [
          { id: 9, kind: "results_xbrl", period_end: "2026-09-30", meta: {}, status: "parsed" },
          { id: 11, kind: "transcript", period_end: "2026-12-31", meta: {}, status: "parsed" },
        ],
      }),
      "POST /api/models/1/sync": () => ({ status: 200, body: { job_id: "j1", status: "queued" } }),
    }),
  );
  renderAt(<Models />);
  await screen.findByText("TCS model");
  fireEvent.click(screen.getByRole("button", { name: /update/i }));
  await waitFor(() =>
    expect(calls.find((c) => c.url === "/api/models/1/sync")?.body).toEqual({ filing_id: 9 }),
  );
});

it("Build opens the build review", async () => {
  mockLock(null);
  renderAt(<Models />);
  await screen.findByText("TCS model");
  fireEvent.click(screen.getByRole("button", { name: /build/i }));
  expect(screen.getByTestId("where").textContent).toBe("/models/1/assumptions");
});

it("Report opens Reports for the model's company", async () => {
  mockLock(null);
  renderAt(<Models />);
  await screen.findByText("TCS model");
  await waitFor(() => expect(disabled(/report/i)).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: /report/i }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/reports?company=TCS"));
});

it("a lock given back on the next poll enables the actions", async () => {
  let held = true;
  mockApi(
    routes(() => ({ status: 200, body: held ? lockOf() : null }), ANALYST, {
      "GET /api/settings/upload-limit": () => ({
        status: 200,
        body: { ...SETTINGS, lock_poll_seconds: 0.05 },
      }),
    }),
  );
  renderAt(<Models />);
  await screen.findByText("In use by Kaushal since 10:42");
  expect(disabled(/update/i)).toBe(true);
  held = false;
  await waitFor(() => expect(screen.queryByText(/In use by/)).toBeNull());
  expect(disabled(/update/i)).toBe(false);
});
