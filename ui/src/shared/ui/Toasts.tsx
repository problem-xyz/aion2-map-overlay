import { useEffect, useRef, useState } from "react";

import type { MessageKey, TFunction } from "@/shared/i18n";
import { useT } from "@/shared/i18n";

import { useToasts, type Toast } from "./ToastProvider";

/** How long a toast the queue has let go of stays drawn, fading: --duration-base, and a frame. */
export const EXIT_MS = 170;

/**
 * A toast is translated when it is drawn, not when it arrives: changing the language repaints
 * whatever is still on screen. `text` is the English Python already formatted, kept as the
 * fallback for a code this build has no message for.
 */
function render(t: TFunction, toast: Toast): string {
  if (!toast.code) return toast.text ?? "";
  const key = `notify.${toast.code}` as MessageKey;
  const translated = t(key, toast.params);
  return translated === key ? (toast.text ?? toast.code) : translated;
}

/**
 * The toasts the queue has just dropped, kept for their fade. The queue itself keeps its promise
 * of TOAST_MS to the millisecond; this is only the picture of it leaving.
 */
function useLeaving(toasts: readonly Toast[]): Toast[] {
  const [leaving, setLeaving] = useState<Toast[]>([]);
  const previous = useRef<readonly Toast[]>(toasts);
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());

  useEffect(() => {
    const now = new Set(toasts.map((t) => t.id));
    const gone = previous.current.filter((t) => !now.has(t.id));
    previous.current = toasts;
    if (gone.length === 0) return;
    setLeaving((list) => [...list, ...gone]);
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      setLeaving((list) => list.filter((t) => !gone.includes(t)));
    }, EXIT_MS);
    timers.current.add(timer);
  }, [toasts]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  return leaving;
}

/**
 * Errors announce themselves; information waits its turn. role="alert" interrupts a screen
 * reader, which is right for a failure and rude for "route saved". A toast on its way out is
 * hidden from the tree at once: it has been said, and its fade is for the eye only.
 *
 * The leaving and the live are drawn as one list in the order they arrived: a toast that moved
 * among its siblings would be re-inserted, and would play its entrance instead of its exit.
 */
export default function Toasts() {
  const { toasts } = useToasts();
  const leaving = useLeaving(toasts);
  const t = useT();
  if (toasts.length === 0 && leaving.length === 0) return null;

  const gone = new Set(leaving.map((toast) => toast.id));
  const all = [...leaving, ...toasts].sort((a, b) => a.id - b.id);

  return (
    <div className="toasts">
      {all.map((toast) =>
        gone.has(toast.id) ? (
          <div key={toast.id} className={`toast toast-${toast.level} leaving`} aria-hidden="true">
            {render(t, toast)}
          </div>
        ) : (
          <div
            key={toast.id}
            className={`toast toast-${toast.level}`}
            role={toast.level === "error" ? "alert" : "status"}
            aria-live={toast.level === "error" ? "assertive" : "polite"}
          >
            {render(t, toast)}
          </div>
        ),
      )}
    </div>
  );
}
