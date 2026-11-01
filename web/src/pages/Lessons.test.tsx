import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Lessons } from "./Lessons";
import { ADMIN, ANALYST, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const lesson = (over: Record<string, unknown>) => ({
  id: 1,
  text: "Never call margins robust",
  scope: "analyst",
  status: "active",
  test_kind: "phrase",
  test_spec: { banned: ["robust"] },
  strength: 2,
  source_thread_id: 7,
  mine: true,
  created_at: "",
  updated_at: "u1",
  ...over,
});
const LESSONS = [lesson({}), lesson({ id: 2, text: "Charts show eight quarters", scope: "firm", mine: false, source_thread_id: null, test_kind: "structure" }), lesson({ id: 3, text: "Old habit", status: "retired" })];

function show(me = ANALYST) {
  return mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: me }),
    "GET /api/lessons": () => ({ status: 200, body: LESSONS }),
    "PATCH /api/lessons/1": () => ({ status: 200, body: lesson({ status: "retired" }) }),
    "POST /api/lessons/1/promote": () => ({ status: 200, body: lesson({ scope: "firm" }) }),
  });
}

it("groups active and retired lessons and marks firm ones", async () => {
  show();
  renderAt(<Lessons />);
  expect(await screen.findByDisplayValue("Never call margins robust")).toBeTruthy();
  expect(screen.getByRole("region", { name: "Retired" })).toBeTruthy();
  expect(screen.getByText("Charts show eight quarters")).toBeTruthy();
  expect(screen.getByText("Firm")).toBeTruthy();
  expect(screen.getAllByText("learnt 2 times").length).toBe(3);
});

it("an analyst retires their own lesson and cannot promote it", async () => {
  const calls = show();
  renderAt(<Lessons />);
  await screen.findByDisplayValue("Never call margins robust");
  expect(screen.queryByRole("button", { name: "Make it a firm lesson" })).toBeNull();
  fireEvent.click(screen.getAllByRole("button", { name: "Retire" })[0]);
  await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
  expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ status: "retired" });
});

it("an admin can make an analyst's lesson a firm lesson", async () => {
  const calls = show(ADMIN);
  renderAt(<Lessons />);
  await screen.findByDisplayValue("Never call margins robust");
  fireEvent.click(screen.getAllByRole("button", { name: "Make it a firm lesson" })[0]);
  await waitFor(() => expect(calls.some((c) => c.url === "/api/lessons/1/promote")).toBe(true));
});
