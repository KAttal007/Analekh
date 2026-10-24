import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { useSignOut } from "../lib/auth";
import { mockApi } from "../test-utils";
import { announceFreed, useFreed } from "./freed";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
);

it("signing out drops every free-model toast and the sign-in reminder's mark", async () => {
  mockApi({ "POST /api/auth/logout": () => ({ status: 204 }) });
  sessionStorage.setItem("analekh.signin-locks", "u1");
  const { result } = renderHook(() => ({ freed: useFreed(), signOut: useSignOut() }), { wrapper });
  act(() => announceFreed({ modelId: 1, to: "/models" }));
  expect(result.current.freed).toHaveLength(1);
  await act(() => result.current.signOut());
  expect(result.current.freed).toHaveLength(0);
  expect(sessionStorage.getItem("analekh.signin-locks")).toBeNull();
});
