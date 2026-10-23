import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { NewPasswordField } from "./PasswordRules";
import { mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// The server's table for the default settings (design doc: spec section 5).
const RULES = {
  rules: [
    { id: "length", label: "15 to 30 characters", pattern: String.raw`^[\s\S]{15,30}$` },
    { id: "letters", label: "At least 8 letters", pattern: "^(?:[^A-Za-z]*[A-Za-z]){8}" },
    { id: "digits", label: "At least 1 number", pattern: "^(?:[^0-9]*[0-9]){1}" },
    {
      id: "specials",
      label: "At least 1 special character",
      pattern: String.raw`^(?:[A-Za-z0-9\s]*[^A-Za-z0-9\s]){1}`,
    },
    { id: "upper", label: "At least 1 uppercase letter", pattern: "^(?:[^A-Z]*[A-Z]){1}" },
    { id: "lower", label: "At least 1 lowercase letter", pattern: "^(?:[^a-z]*[a-z]){1}" },
    { id: "no_spaces", label: "No spaces", pattern: String.raw`^\S*$` },
  ],
  combined: "",
  max_length: 30,
  min_length: 15,
};
const routes = (over: Partial<typeof RULES> = {}) => ({
  "GET /api/auth/password-rules": () => ({ status: 200, body: { ...RULES, ...over } }),
});

function Host() {
  const [value, setValue] = useState("");
  return <NewPasswordField value={value} onChange={setValue} />;
}

const ticked = () =>
  screen.getAllByRole("listitem").map((li) => li.getAttribute("data-met") === "true");
const type = (value: string) =>
  fireEvent.change(screen.getByLabelText("New password"), { target: { value } });

async function show() {
  mockApi(routes());
  renderAt(<Host />);
  await screen.findByText("No spaces");
}

test("ticks each rule as typed", async () => {
  await show();
  expect(ticked()).toEqual([false, false, false, false, false, false, true]);
  type("Abcdefgh12345!x");
  expect(ticked()).toEqual([true, true, true, true, true, true, true]);
});

test("never puts the value in the DOM as markup", async () => {
  await show();
  type("<script>alert(1)</script>Aa1");
  expect(document.querySelector("script")).toBeNull();
  // Only the input's value attribute holds it; the rules list and the rest of the page do not.
  expect(document.querySelector("ul")!.innerHTML).not.toContain("alert(1)");
  expect(document.body.textContent).not.toContain("alert(1)");
});

test("maxLength comes from the rules reply", async () => {
  mockApi(routes({ max_length: 30 }));
  renderAt(<Host />);
  await waitFor(() =>
    expect((screen.getByLabelText("New password") as HTMLInputElement).maxLength).toBe(30),
  );
});

test("patterns agree with the server table", async () => {
  await show();
  // [password, ticks the Python side gives for the seven rules, in order]
  const cases: [string, boolean[]][] = [
    ["", [false, false, false, false, false, false, true]],
    ["abcdefgh", [false, true, false, false, false, true, true]],
    ["ABCDEFGH", [false, true, false, false, true, false, true]],
    ["Abcdefg1", [false, false, true, false, true, true, true]],
    ["Abcdefgh1!", [false, true, true, true, true, true, true]],
    ["Abcdefgh1! xyzabc", [true, true, true, true, true, true, false]],
    ["Abcdefgh1!xyzab", [true, true, true, true, true, true, true]],
    ["Abcdefgh1!xyzabcdefghijklmnopqrs", [false, true, true, true, true, true, true]],
    ["12345678901234567890!", [true, false, true, true, false, false, true]],
  ];
  for (const [pw, want] of cases) {
    type(pw);
    expect(ticked(), pw).toEqual(want);
  }
});

test("the input is a password box that asks for a new password, with a polite list", async () => {
  await show();
  const input = screen.getByLabelText("New password") as HTMLInputElement;
  expect(input.type).toBe("password");
  expect(input.autocomplete).toBe("new-password");
  expect(screen.getByRole("list").getAttribute("aria-live")).toBe("polite");
});
