import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { ApiError, onSignedOut } from "./api/client";
import { ME_KEY } from "./lib/auth";
import { router } from "./router";
import "@fontsource-variable/inter";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      retry: (failures, error) => failures < 1 && !(error instanceof ApiError && (error.status < 500 || error.status === 503)),
    },
  },
});

onSignedOut(() => queryClient.setQueryData(ME_KEY, null));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
