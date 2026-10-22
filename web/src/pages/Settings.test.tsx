import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { Settings } from "./Settings";
import { ANALYST, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const TOKENS = [{ id: 7, name: "Office laptop", created_at: "2026-10-20T09:00:00Z" }];
const base = () => ({
  "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
  "GET /api/auth/tokens": () => ({ status: 200, body: TOKENS }),
});

test("personal settings no longer carry data status or alerts", async () => {
  mockApi(base());
  renderAt(<Settings />);
  await screen.findByText("Office laptop");
  expect(screen.queryByText("Data status")).toBeNull();
  expect(screen.queryByText("Alerts")).toBeNull();
});

test("a new bridge token is shown once, with its name", async () => {
  const calls = mockApi({
    ...base(),
    "POST /api/auth/tokens": () => ({
      status: 201,
      body: {
        id: 8,
        name: "Home PC",
        created_at: "2026-10-22T09:00:00Z",
        token: "secret-token-value",
      },
    }),
  });
  renderAt(<Settings />);
  fireEvent.change(await screen.findByLabelText("Token name"), { target: { value: "Home PC" } });
  fireEvent.click(screen.getByRole("button", { name: "Create token" }));
  expect((await screen.findByText("secret-token-value")).textContent).toBe("secret-token-value");
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ name: "Home PC" });
  expect(screen.getByText(/shown only once/i)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(screen.queryByText("secret-token-value")).toBeNull();
});

test("sign out everywhere asks first, then posts once", async () => {
  const calls = mockApi({
    ...base(),
    "POST /api/auth/logout-everywhere": () => ({ status: 204 }),
  });
  renderAt(<Settings />);
  await screen.findByText("Office laptop");
  fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
  expect(calls.some((c) => c.url === "/api/auth/logout-everywhere")).toBe(false);
  expect(screen.getByText(/revokes your Excel bridge tokens/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Sign out everywhere" }));
  const buttons = screen.getAllByRole("button", { name: "Sign out everywhere" });
  fireEvent.click(buttons[buttons.length - 1]);
  await waitFor(() =>
    expect(calls.filter((c) => c.url === "/api/auth/logout-everywhere")).toHaveLength(1),
  );
  expect(calls.some((c) => c.url === "/api/auth/logout")).toBe(false);
});

test("a token can be revoked", async () => {
  const calls = mockApi({ ...base(), "DELETE /api/auth/tokens/7": () => ({ status: 204 }) });
  renderAt(<Settings />);
  fireEvent.click(await screen.findByRole("button", { name: "Revoke Office laptop" }));
  await waitFor(() =>
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/auth/tokens/7")).toBe(true),
  );
});
