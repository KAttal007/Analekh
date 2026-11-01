import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Qa } from "./Qa";
import { mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const SUMMARY = { id: 3, symbol: "TCS", company_name: "TCS Limited", title: "What was NIM?", busy: false, updated_at: "2026-11-02T10:00:00Z" };
const CHAT = {
  ...SUMMARY,
  messages: [
    { id: 1, role: "analyst", body: "What was NIM?", meta: null, created_at: "" },
    { id: 2, role: "ai", body: "NIM was 3.4%.", meta: { blocked: false, unmatched: [], citations: [{ filing_id: 4, page: 7 }] }, created_at: "" },
    { id: 3, role: "ai", body: "Answer withheld: it contained numbers that could not be sourced.", meta: { blocked: true, unmatched: ["9.9%"], citations: [] }, created_at: "" },
  ],
};

function show() {
  return mockApi({
    "GET /api/qa/threads": () => ({ status: 200, body: [SUMMARY] }),
    "GET /api/qa/threads/3": () => ({ status: 200, body: CHAT }),
    "POST /api/qa/threads/3/messages": () => ({ status: 200, body: { job_id: "j" } }),
    "GET /api/companies/index": () => ({ status: 200, body: [] }),
  });
}

it("lists chats, shows an answer's page sources and a withheld answer's figures", async () => {
  show();
  renderAt(<Qa />, "/qa?chat=3");
  expect(await screen.findByText("NIM was 3.4%.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "filing 4, page 7" })).toBeTruthy();
  expect(screen.getByText(/could not be sourced: 9.9%/)).toBeTruthy();
  expect(screen.getByRole("button", { name: /What was NIM\?/ }).getAttribute("aria-pressed")).toBe("true");
});

it("asking sends the question to the open chat", async () => {
  const calls = show();
  renderAt(<Qa />, "/qa?chat=3");
  await screen.findByText("NIM was 3.4%.");
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "And cost of funds?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ question: "And cost of funds?" });
});

it("with no chat open it asks for a company", async () => {
  show();
  renderAt(<Qa />, "/qa");
  expect(await screen.findByText("Pick a company to start")).toBeTruthy();
});
