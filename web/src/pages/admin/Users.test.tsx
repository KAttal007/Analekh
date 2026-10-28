import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { Users } from "./Users";
import { ADMIN, mockApi, renderAt } from "../../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const row = (over: object) => ({
  id: "x",
  email: "x@firm.in",
  name: "X",
  role: "analyst",
  auth_kind: "password",
  is_active: true,
  blocked: false,
  created_at: "2026-10-01T00:00:00Z",
  ...over,
});
const USERS = [
  row({ id: "a1", name: "Rhea Mehta", email: "rhea@firm.in", role: "admin" }),
  row({ id: "u2", name: "Arjun Shah", email: "arjun@firm.in", blocked: true }),
  row({ id: "u3", name: "Vikram Patel", email: "vikram@firm.in", is_active: false }),
  row({ id: "u1", name: "Kaushal Attal", email: "kaushal@firm.in" }),
];
const base = () => ({
  "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
  "GET /api/users": () => ({ status: 200, body: USERS }),
});
const rowOf = (name: string) => screen.getByText(name).closest("tr")!;

test("lists everyone with role and status", async () => {
  mockApi(base());
  renderAt(<Users />);
  await screen.findByText("Arjun Shah");
  expect(within(rowOf("Arjun Shah")).getByText("Blocked")).toBeTruthy();
  expect(within(rowOf("Vikram Patel")).getByText("Disabled")).toBeTruthy();
  expect(within(rowOf("Rhea Mehta")).getByText("Admin")).toBeTruthy();
});

test("a blocked user can be unblocked; the others cannot", async () => {
  const calls = mockApi({ ...base(), "POST /api/users/u2/unblock": () => ({ status: 204 }) });
  renderAt(<Users />);
  await screen.findByText("Arjun Shah");
  fireEvent.click(within(rowOf("Arjun Shah")).getByRole("button", { name: "Unblock" }));
  await waitFor(() => expect(calls.some((c) => c.url === "/api/users/u2/unblock")).toBe(true));
  expect(within(rowOf("Kaushal Attal")).queryByRole("button", { name: "Unblock" })).toBeNull();
});

test("disable and enable send a PATCH", async () => {
  const calls = mockApi({
    ...base(),
    "PATCH /api/users/u1": () => ({ status: 200, body: USERS[3] }),
    "PATCH /api/users/u3": () => ({ status: 200, body: USERS[2] }),
  });
  renderAt(<Users />);
  await screen.findByText("Kaushal Attal");
  fireEvent.click(within(rowOf("Kaushal Attal")).getByRole("button", { name: "Disable" }));
  await waitFor(() => expect(calls.find((c) => c.url === "/api/users/u1")?.body).toEqual({ is_active: false }));
  fireEvent.click(within(rowOf("Vikram Patel")).getByRole("button", { name: "Enable" }));
  await waitFor(() => expect(calls.find((c) => c.url === "/api/users/u3")?.body).toEqual({ is_active: true }));
});

test("the server's refusal to remove the last admin is shown as it is", async () => {
  mockApi({
    ...base(),
    "PATCH /api/users/a1": () => ({
      status: 400,
      body: { detail: "There must be at least one active admin." },
    }),
  });
  renderAt(<Users />);
  await screen.findByText("Rhea Mehta");
  fireEvent.click(within(rowOf("Rhea Mehta")).getByRole("button", { name: "Disable" }));
  expect((await screen.findByRole("alert")).textContent).toContain("There must be at least one active admin.");
});

test("a role can be changed from the row", async () => {
  const calls = mockApi({
    ...base(),
    "PATCH /api/users/u1": () => ({ status: 200, body: USERS[3] }),
  });
  renderAt(<Users />);
  await screen.findByText("Kaushal Attal");
  fireEvent.click(within(rowOf("Kaushal Attal")).getByRole("button", { name: "Make admin" }));
  await waitFor(() => expect(calls.find((c) => c.url === "/api/users/u1")?.body).toEqual({ role: "admin" }));
});

test("has no password box in Add user", async () => {
  mockApi(base());
  renderAt(<Users />);
  fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
  expect(screen.queryByLabelText(/password/i)).toBeNull();
  expect(screen.getByText("We email them a first password. They choose their own the first time they sign in.")).toBeTruthy();
});

const added = (final: "sent" | "failed") => {
  let listed = false;
  let mail: string = "sending";
  return {
    "GET /api/users": () => {
      const now = listed
        ? [
            ...USERS,
            row({
              id: "n1",
              name: "Meera Kapoor",
              email: "meera@firm.in",
              first_password_mail: mail,
            }),
          ]
        : USERS;
      if (listed) mail = final; // the next look finds it done
      return { status: 200, body: now };
    },
    "POST /api/users": () => {
      listed = true;
      return {
        status: 201,
        body: row({
          id: "n1",
          name: "Meera Kapoor",
          email: "meera@firm.in",
          first_password_mail: "sending",
        }),
      };
    },
  };
};

const addMeera = async () => {
  renderAt(<Users />);
  fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Meera Kapoor" } });
  fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "meera@firm.in" } });
};

test("adding a user posts name, email and role, then says the email went", async () => {
  const calls = mockApi({ ...base(), ...added("sent") });
  await addMeera();
  fireEvent.click(screen.getByRole("radio", { name: "Admin" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add user" }));
  expect(await screen.findByText(/emailing a first password to meera@firm.in/i)).toBeTruthy();
  expect(await screen.findByText(/first password has been emailed to meera@firm.in/i, {}, { timeout: 4000 })).toBeTruthy();
  expect(calls.find((c) => c.method === "POST" && c.url === "/api/users")?.body).toEqual({
    name: "Meera Kapoor",
    email: "meera@firm.in",
    role: "admin",
  });
  expect(screen.queryByText(/welcome email was not sent/i)).toBeNull();
});

test("shows the not-sent warning and Send again", async () => {
  const calls = mockApi({
    ...base(),
    ...added("failed"),
    "POST /api/users/n1/send-first-password": () => ({
      status: 202,
      body: row({
        id: "n1",
        name: "Meera Kapoor",
        email: "meera@firm.in",
        first_password_mail: "sending",
      }),
    }),
  });
  await addMeera();
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add user" }));
  expect((await screen.findByRole("alert", {}, { timeout: 4000 })).textContent).toContain("The welcome email was not sent.");
  expect(within(rowOf("Meera Kapoor")).getByText("Email not sent")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Send again" }));
  await waitFor(() => expect(calls.some((c) => c.url === "/api/users/n1/send-first-password")).toBe(true));
});

test("add user shows the server reason (duplicate, email not set up)", async () => {
  mockApi({
    ...base(),
    "POST /api/users": () => ({
      status: 409,
      body: { detail: "a user with this email already exists" },
    }),
  });
  renderAt(<Users />);
  fireEvent.click(await screen.findByRole("button", { name: "Add user" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "A" } });
  fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "a@firm.in" } });
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add user" }));
  expect((await screen.findByRole("alert")).textContent).toContain("already exists");
});

test("an active user gets Reset password, and it posts on confirm", async () => {
  const calls = mockApi({
    ...base(),
    "POST /api/users/u1/send-first-password": () => ({ status: 202, body: USERS[3] }),
  });
  renderAt(<Users />);
  await screen.findByText("Kaushal Attal");
  expect(screen.queryByRole("button", { name: "Send first password" })).toBeNull();
  fireEvent.click(within(rowOf("Kaushal Attal")).getByRole("button", { name: "Reset password" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Reset Kaushal Attal's password?")).toBeTruthy();
  expect(within(dialog).getByText(/current password stops working/i)).toBeTruthy();
  expect(calls.some((c) => c.url === "/api/users/u1/send-first-password")).toBe(false);
  fireEvent.click(within(dialog).getByRole("button", { name: "Reset password" }));
  await waitFor(() => expect(calls.some((c) => c.url === "/api/users/u1/send-first-password")).toBe(true));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("sending a first password says so when email is not set up", async () => {
  mockApi({
    ...base(),
    "POST /api/users/u1/send-first-password": () => ({
      status: 503,
      body: { detail: "Email is not set up. Contact the admin team." },
    }),
  });
  renderAt(<Users />);
  await screen.findByText("Kaushal Attal");
  fireEvent.click(within(rowOf("Kaushal Attal")).getByRole("button", { name: "Reset password" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reset password" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Email is not set up");
});

test("a user waiting for the first sign-in gets Send first password", async () => {
  mockApi({
    ...base(),
    "GET /api/users": () => ({
      status: 200,
      body: [row({ id: "w1", name: "Waiting Now", must_change_password: true })],
    }),
  });
  renderAt(<Users />);
  await screen.findByText("Waiting Now");
  fireEvent.click(within(rowOf("Waiting Now")).getByRole("button", { name: "Send first password" }));
  expect(within(screen.getByRole("dialog")).getByText("Send Waiting Now a new first password?")).toBeTruthy();
});

test("an account still on its first password is tagged", async () => {
  mockApi({
    ...base(),
    "GET /api/users": () => ({
      status: 200,
      body: [row({ id: "w1", name: "Waiting Now", must_change_password: true }), row({ id: "w2", name: "Settled Down", must_change_password: false })],
    }),
  });
  renderAt(<Users />);
  await screen.findByText("Waiting Now");
  expect(within(rowOf("Waiting Now")).getByText("Waiting for first sign-in")).toBeTruthy();
  expect(within(rowOf("Settled Down")).queryByText("Waiting for first sign-in")).toBeNull();
});

test("shows when each user was last seen, and a current pause", async () => {
  mockApi({
    ...base(),
    "GET /api/users": () => ({
      status: 200,
      body: [row({ id: "s1", name: "Seen Once", last_seen_at: "2026-10-22T04:12:00Z" }), row({ id: "p1", name: "Paused Now", paused_until: "2026-10-22T05:00:00Z" })],
    }),
  });
  renderAt(<Users />);
  await screen.findByText("Seen Once");
  expect(within(rowOf("Seen Once")).getByText(/22 Oct.*9:42/)).toBeTruthy(); // India time
  expect(within(rowOf("Paused Now")).getByText("Never")).toBeTruthy();
  expect(within(rowOf("Paused Now")).getByText(/Paused until 22 Oct.*10:30/)).toBeTruthy();
});

test("search narrows the list by name or email", async () => {
  mockApi(base());
  renderAt(<Users />);
  await screen.findByText("Arjun Shah");
  fireEvent.change(screen.getByPlaceholderText("Search name or email"), {
    target: { value: "vikram" },
  });
  expect(screen.queryByText("Arjun Shah")).toBeNull();
  expect(screen.getByText("Vikram Patel")).toBeTruthy();
});
