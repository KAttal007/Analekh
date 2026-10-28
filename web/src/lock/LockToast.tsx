import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { companyIndexQuery } from "../lib/preload";
import { dismissFreed, type Freed, useFreed } from "./freed";
import { lockKey } from "./useModelLock";

/** A model the viewer waited for is free. Appears at once (no entrance motion) and stays until
 *  dismissed or opened. */
export function LockToast({ companyName, modelId, onOpen, onDismiss }: { companyName: string; modelId: number; onOpen(): void; onDismiss?(): void }) {
  return (
    <div className="lock-toast" role="status" data-model={modelId}>
      <Icon name="check" />
      <button type="button" className="lock-toast-open" onClick={onOpen}>
        {companyName}'s model is free. You can open it for editing.
      </button>
      {onDismiss && (
        <button type="button" className="icon-btn lock-toast-close" aria-label="Dismiss" title="Dismiss" onClick={onDismiss}>
          <Icon name="x" size={14} />
        </button>
      )}
    </div>
  );
}

/** One freed model: the company's name comes from the cached model list and company index. */
function FreedToast({ item }: { item: Freed }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const index = useQuery(companyIndexQuery);
  const companyId = models.data?.find((m) => m.id === item.modelId)?.company_id;
  const name = index.data?.find((c) => c.id === companyId)?.name;
  const failed = models.isError || index.isError || (models.isSuccess && companyId === undefined);
  if (!name && !failed) return null; // known in a moment: both lists are normally cached
  return (
    <LockToast
      companyName={name ?? `Model ${item.modelId}`}
      modelId={item.modelId}
      onOpen={() => {
        dismissFreed(item.modelId);
        void qc.invalidateQueries({ queryKey: lockKey(item.modelId) });
        navigate(item.to);
      }}
      onDismiss={() => dismissFreed(item.modelId)}
    />
  );
}

/** Every waiting free-model toast, in the corner of the app. */
export function LockToasts() {
  const freed = useFreed();
  if (!freed.length) return null;
  return (
    <div className="lock-toasts" aria-live="polite">
      {freed.map((f) => (
        <FreedToast key={f.modelId} item={f} />
      ))}
    </div>
  );
}
