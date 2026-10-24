import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type LockOut } from "../api/client";
import { companyIndexQuery } from "../lib/preload";
import { lockKey } from "./useModelLock";

// What the sign-in and idle reminders share: the user's own locks, the company each model
// belongs to, and giving a lock back.

export const meLocksKey = ["me-locks"] as const;

/** Each model's company name, from the cached model list and company index (as the free-model
 *  toast finds it). `ready` once both are in, or one failed: then `Model {id}` stands in. */
export function useCompanyNames(enabled: boolean) {
  const models = useQuery({ queryKey: ["models"], queryFn: api.models, enabled });
  const index = useQuery({ ...companyIndexQuery, enabled });
  const failed = models.isError || index.isError;
  const ready = (models.isSuccess && index.isSuccess) || failed;
  const name = (modelId: number): string => {
    const companyId = models.data?.find((m) => m.id === modelId)?.company_id;
    return index.data?.find((c) => c.id === companyId)?.name ?? `Model ${modelId}`;
  };
  return { ready, name };
}

/** Give one of the user's own locks back (the holder route), then drop it from the lists. */
export function useReleaseMine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (modelId: number) => api.releaseLock(modelId),
    onSuccess: (_, modelId) => {
      qc.setQueryData<LockOut[]>(meLocksKey, (held) => held?.filter((l) => l.model_id !== modelId));
      void qc.invalidateQueries({ queryKey: meLocksKey });
      void qc.invalidateQueries({ queryKey: lockKey(modelId) });
    },
  });
}
