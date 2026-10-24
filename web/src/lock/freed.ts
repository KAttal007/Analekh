import { useSyncExternalStore } from "react";
import { readPrefs } from "../lib/prefs";
import { playChime } from "./chime";

// Models a colleague gave back while the viewer waited (model locks): one toast per model, kept
// until the viewer dismisses or opens it. The lock hook announces; LockToasts (in the layout)
// shows them.

export type Freed = { modelId: number; to: string };

let freed: Freed[] = [];
const listeners = new Set<() => void>();
const changed = () => listeners.forEach((l) => l());

/** A model this viewer saw held is free: add its toast (once) and chime if the user wants. */
export function announceFreed(item: Freed): void {
  freed = [...freed.filter((f) => f.modelId !== item.modelId), item];
  changed();
  playChime(readPrefs().chime);
}

export function dismissFreed(modelId: number): void {
  freed = freed.filter((f) => f.modelId !== modelId);
  changed();
}

/** Drop every toast (tests). */
export function clearFreed(): void {
  freed = [];
  changed();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

export function useFreed(): Freed[] {
  return useSyncExternalStore(
    subscribe,
    () => freed,
    () => freed,
  );
}
