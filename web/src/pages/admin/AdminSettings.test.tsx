import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { AdminSettings } from "./AdminSettings";
import { ADMIN, mockApi, renderAt } from "../../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const MB = 1024 * 1024;
const LIMIT = {
  bytes: 25 * MB,
  ceiling_bytes: 100 * MB,
  min_bytes: MB,
  updated_by: "a1",
  updated_at: "2026-10-14T15:20:00Z",
};
const quiet = {
  "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
  "GET /api/users": () => ({
    status: 200,
    body: [{ ...ADMIN, auth_kind: "password", is_active: true, blocked: false }],
  }),
  "GET /api/status": () => ({ status: 500, body: { detail: "off" } }),
  "GET /api/alerts/channels": () => ({ status: 500, body: { detail: "off" } }),
  "GET /api/alerts": () => ({ status: 200, body: [] }),
};
const limitInput = async () => (await screen.findByLabelText("Maximum file size")) as HTMLInputElement;

test("the upload-limit card shows the current limit and who changed it", async () => {
  mockApi({ ...quiet, "GET /api/settings/upload-limit": () => ({ status: 200, body: LIMIT }) });
  renderAt(<AdminSettings />);
  expect((await screen.findByText("25 MB")).textContent).toBe("25 MB");
  expect(screen.getByText(/Rhea Mehta/)).toBeTruthy();
  expect((await limitInput()).value).toBe("25");
  expect(screen.getByText(/1 to 100 MB/)).toBeTruthy();
});

test("saving sends the size in bytes", async () => {
  const calls = mockApi({
    ...quiet,
    "GET /api/settings/upload-limit": () => ({ status: 200, body: LIMIT }),
    "PUT /api/settings/upload-limit": () => ({ status: 200, body: { ...LIMIT, bytes: 40 * MB } }),
  });
  renderAt(<AdminSettings />);
  fireEvent.change(await limitInput(), { target: { value: "40" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ bytes: 40 * MB }));
});

test("a value above the ceiling shows the server's text and keeps what was typed", async () => {
  mockApi({
    ...quiet,
    "GET /api/settings/upload-limit": () => ({ status: 200, body: LIMIT }),
    "PUT /api/settings/upload-limit": () => ({
      status: 422,
      body: { detail: "The limit must be between 1 MB and 100 MB." },
    }),
  });
  renderAt(<AdminSettings />);
  const input = await limitInput();
  fireEvent.change(input, { target: { value: "500" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const shown = await screen.findByText("The limit must be between 1 MB and 100 MB.");
  expect(shown.getAttribute("role")).toBe("alert");
  expect(input.value).toBe("500");
});

test("a non-number is refused before anything is sent", async () => {
  const calls = mockApi({
    ...quiet,
    "GET /api/settings/upload-limit": () => ({ status: 200, body: LIMIT }),
  });
  renderAt(<AdminSettings />);
  fireEvent.change(await limitInput(), { target: { value: "abc" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const shown = await screen.findByText("Enter a number of megabytes.");
  expect(shown.getAttribute("role")).toBe("alert");
  expect(calls.some((c) => c.method === "PUT")).toBe(false);
});
