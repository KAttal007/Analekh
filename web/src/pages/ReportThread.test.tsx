import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ReportThread } from "./ReportThread";
import { type Handler, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const DRAFT = {
  schema_version: 1,
  format: "word",
  units: [
    { title: "Results highlights", blocks: [{ type: "paragraph", text: "Margins hit 18.2% now." }] },
    { title: "Rating, target price and guidance", blocks: [{ type: "placeholder", kind: "rating" }] },
  ],
};
const THREAD = {
  id: 7,
  symbol: "TCS",
  company_name: "TCS Limited",
  report_type: "quarterly",
  format: "word",
  quarter_end: "2026-09-30",
  status: "drafting",
  busy: false,
  updated_at: "2026-11-02T10:00:00Z",
  basis: "standalone",
  current_version: 2,
  unsourced: ["18.2%"],
  draft: DRAFT,
  messages: [
    {
      id: 1,
      role: "ai",
      body: "Here is the first draft.",
      selection: null,
      created_at: "2026-11-02T10:00:00Z",
      meta: { version_no: 2, changed_units: [0], blocked: [{ unit: 2, unmatched: ["14.0%"], style: [], lessons: [] }] },
    },
  ],
};

function show(over: Record<string, unknown> = {}, extra: Record<string, Handler> = {}) {
  const calls = mockApi({
    "GET /api/threads/7": () => ({ status: 200, body: { ...THREAD, ...over } }),
    ...extra,
  });
  renderAt(
    <Routes>
      <Route path="/reports/:id" element={<ReportThread />} />
    </Routes>,
    "/reports/7",
  );
  return calls;
}

it("shows the draft, the not-sourced marker, the analyst's blanks and why a section was not drafted", async () => {
  show();
  expect(await screen.findByDisplayValue("Margins hit 18.2% now.")).toBeTruthy();
  expect(screen.getByText("Not sourced: 18.2%")).toBeTruthy();
  expect(screen.getByText(/You add this in the file/)).toBeTruthy();
  expect(screen.getByText(/Section 3 was not changed/)).toBeTruthy();
});

it("a typed edit is saved on leaving the field, against the version on screen", async () => {
  const calls = show({}, { "PUT /api/threads/7/draft": () => ({ status: 200, body: { version_no: 3, unsourced: [] } }) });
  const box = await screen.findByDisplayValue("Margins hit 18.2% now.");
  fireEvent.change(box, { target: { value: "Margins steady." } });
  fireEvent.blur(box);
  await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  const put = calls.find((c) => c.method === "PUT")!;
  expect((put.body as { base_version: number }).base_version).toBe(2);
  expect(JSON.stringify(put.body)).toContain("Margins steady.");
});

it("while the AI writes, the draft is read-only and Send waits", async () => {
  show({ busy: true });
  const box = (await screen.findByDisplayValue("Margins hit 18.2% now.")) as HTMLTextAreaElement;
  expect(box.readOnly).toBe(true);
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "shorter" } });
  expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByLabelText("The AI is writing")).toBeTruthy();
});

it("a message about one section carries the selection and the version", async () => {
  const calls = show({}, { "POST /api/threads/7/messages": () => ({ status: 200, body: { job_id: "j" } }) });
  await screen.findByDisplayValue("Margins hit 18.2% now.");
  fireEvent.click(screen.getAllByRole("button", { name: "Ask about this" })[0]);
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Lead with NIM" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ message: "Lead with NIM", base_version: 2, selection: { unit: 0 } });
});

it("approving asks first and says how many figures are not sourced", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  const calls = show({}, { "POST /api/threads/7/approve": () => ({ status: 200, body: { version_no: 3, unsourced_count: 1 } }) });
  fireEvent.click(await screen.findByRole("button", { name: /Approve draft/ }));
  await waitFor(() => expect(calls.some((c) => c.url === "/api/threads/7/approve")).toBe(true));
  expect(confirm.mock.calls[0][0]).toContain("1 figure is not sourced");
});

it("once approved: download, publish, and the chat is closed", async () => {
  show({ status: "approved" });
  const link = (await screen.findByRole("link", { name: /Download the Word file/ })) as HTMLAnchorElement;
  expect(link.getAttribute("href")).toBe("/api/threads/7/file");
  expect(screen.getByLabelText("Final file")).toBeTruthy();
  expect((screen.getByLabelText("Message") as HTMLTextAreaElement).disabled).toBe(true);
  expect(screen.queryByRole("button", { name: /Approve draft/ })).toBeNull();
});

it("a file without the report tag is published only after the analyst confirms", async () => {
  let tries = 0;
  const calls = show(
    { status: "approved" },
    {
      "POST /api/threads/7/publish": () => {
        tries += 1;
        return tries === 1 ? { status: 422, body: { detail: { code: "no_tag", message: "no tag" } } } : { status: 200, body: { id: 1, thread_id: 7, extension: ".docx", has_macros: false, route: "upload", created_at: "" } };
      },
    },
  );
  const input = await screen.findByLabelText("Final file");
  fireEvent.change(input, { target: { files: [new File(["x"], "final.docx")] } });
  fireEvent.click(await screen.findByRole("button", { name: "Yes, publish it" }));
  await waitFor(() => expect(tries).toBe(2));
  const second = calls.filter((c) => c.url === "/api/threads/7/publish")[1].init.body as FormData;
  expect(second.get("confirmed")).toBe("true");
});
