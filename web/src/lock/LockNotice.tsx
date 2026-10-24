import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { ErrorNote } from "../components/ui";
import { useMe } from "../lib/auth";
import { ReadOnlyBanner } from "./ReadOnlyBanner";
import type { useModelLock } from "./useModelLock";

type Gate = ReturnType<typeof useModelLock>;

/** Whether the signed-in user is an admin: admins free a held model instead of working on it. */
export function useIsAdmin(): boolean {
  return useMe().data?.role === "admin";
}

/** The read-only banner while a colleague holds the model, with Release lock for an admin. */
export function LockNotice({ modelId, gate }: { modelId: number; gate: Gate }) {
  const isAdmin = useIsAdmin();
  const release = useMutation({
    mutationFn: () => api.adminReleaseLock(modelId),
    onMutate: () => gate.releasing(true), // the admin freed it: no "is free" toast for them
    onError: () => gate.releasing(false),
    onSettled: gate.refresh,
  });
  if (!gate.held || !gate.lock) return null;
  return (
    <>
      <ReadOnlyBanner
        holderName={gate.lock.holder_name}
        takenAt={gate.lock.taken_at}
        action={
          isAdmin && (
            <button
              type="button"
              className="btn-sm"
              onClick={() => release.mutate()}
              disabled={release.isPending}
            >
              Release lock
            </button>
          )
        }
      />
      {release.isError && <ErrorNote error={release.error} />}
    </>
  );
}
