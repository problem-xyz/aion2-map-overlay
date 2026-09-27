import { useEffect, useState, type ReactNode } from "react";

/** When the sections are drawn: after the panel's own first frames, and for how long. */
export const WARM_DELAY_MS = 400;
export const WARM_HOLD_MS = 1200;

export interface WarmUpProps {
  /** The sections that are not on screen. */
  children: ReactNode;
}

/**
 * Draws the sections that are not on screen once, while the panel opens, and takes them away.
 *
 * The first time a section showed, the panel froze for 200-400ms (measured in QtWebEngine: the
 * progress list's icons and check boxes, the sliders): no script and no layout, the GPU
 * building what it had not drawn before. A persistent profile keeps nothing that helps -- the
 * next launch froze the same. So the cost is paid here, while the window is only appearing,
 * instead of on the user's first click.
 *
 * They are drawn for real, at full size, but all but transparent, behind the page, inert and
 * hidden from assistive technology: nothing reaches them, and nothing about them is read out.
 */
export default function WarmUp({ children }: WarmUpProps) {
  const [phase, setPhase] = useState<"wait" | "draw" | "done">("wait");

  useEffect(() => {
    if (phase === "done") return undefined;
    const timer = window.setTimeout(
      () => setPhase(phase === "wait" ? "draw" : "done"),
      phase === "wait" ? WARM_DELAY_MS : WARM_HOLD_MS,
    );
    return () => window.clearTimeout(timer);
  }, [phase]);

  if (phase !== "draw") return null;
  return (
    <div
      className="pn-warm"
      aria-hidden="true"
      // React 18 has no inert prop; the attribute keeps focus and the pointer out
      ref={(node) => node?.setAttribute("inert", "")}
    >
      <div className="app">{children}</div>
    </div>
  );
}
