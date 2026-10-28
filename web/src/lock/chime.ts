// The free-model chime (model locks): a short, soft 660 Hz tone. With the reminder pop-up it is
// the only attention the app asks for unprompted, so it stays quiet whenever it can: off in
// Settings, under reduced motion, without Web Audio, or within a second of the last chime (two
// models freed together make one sound). It never throws.

const GAP_MS = 1000;
const TONE_S = 0.25;
const PEAK = 0.06; // soft: well under full volume

type Ctor = new () => AudioContext;

let ctx: AudioContext | null = null; // one per page, reused
let lastAt = Number.NEGATIVE_INFINITY;

/** Forget the shared AudioContext and the last chime (tests). */
export function resetChime(): void {
  ctx = null;
  lastAt = Number.NEGATIVE_INFINITY;
}

const audioCtor = (): Ctor | undefined =>
  (window as unknown as { AudioContext?: Ctor; webkitAudioContext?: Ctor }).AudioContext ?? (window as unknown as { webkitAudioContext?: Ctor }).webkitAudioContext;

/** Create or wake the shared AudioContext. Only works inside a user gesture: browsers start one
 *  made without a gesture suspended, so the idle reminder's chime would be silent. */
function wake(): void {
  try {
    const Audio = audioCtor();
    if (!Audio) return;
    ctx ??= new Audio();
    if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
  } catch {
    /* audio blocked or unavailable: the chime stays silent */
  }
}

/** Wake the AudioContext on the user's clicks and key presses (the first one creates it), so a
 *  later chime nobody clicked for can play. Returns the function that stops listening. */
export function unlockChimeOnGesture(): () => void {
  const opts = { capture: true, passive: true } as const;
  window.addEventListener("pointerdown", wake, opts);
  window.addEventListener("keydown", wake, opts);
  return () => {
    window.removeEventListener("pointerdown", wake, opts);
    window.removeEventListener("keydown", wake, opts);
  };
}

export function playChime(enabled: boolean): void {
  if (!enabled) return;
  try {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const now = Date.now();
    if (now - lastAt < GAP_MS) return;
    const Audio = audioCtor();
    if (!Audio) return;
    ctx ??= new Audio();
    if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
    lastAt = now;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = 660;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(PEAK, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + TONE_S);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + TONE_S);
  } catch {
    /* audio blocked or unavailable: the toast alone is enough */
  }
}
