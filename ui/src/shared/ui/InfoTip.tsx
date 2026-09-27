import { useCallback, useEffect, useId, useRef, type ReactNode } from "react";

import { useT } from "@/shared/i18n";

import Icon from "./Icon";

const GAP = 6; // between the field's head and the tip
const HIDE_DELAY = 120; // long enough to move the pointer from the button onto the tip

export interface InfoTipProps {
  /** The name of what it explains: the button is announced as "About <topic>". */
  topic: string;
  children: ReactNode;
}

/**
 * A small "i" beside a field's label, and the longer explanation it opens.
 *
 * The tip is a manual popover, so it sits in the top layer: a card that clips its content --
 * the Advanced section does while it folds -- cannot cut it off. It spans the field it belongs
 * to, below the field's head or above it when the window has no room underneath.
 *
 * It opens on hover, on focus and on a click (a touch screen has no hover), stays open while
 * the pointer is over the tip itself, and closes on Escape and on a scroll. The text is the
 * button's description as well, so a screen reader reads it out without opening anything.
 */
export default function InfoTip({ topic, children }: InfoTipProps) {
  const t = useT();
  const id = useId();
  const button = useRef<HTMLButtonElement | null>(null);
  const tip = useRef<HTMLDivElement | null>(null);
  const timer = useRef<number | null>(null);

  const cancelHide = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const hide = useCallback(() => {
    cancelHide();
    const el = tip.current;
    if (el?.matches(":popover-open")) el.hidePopover();
  }, [cancelHide]);

  const hideSoon = useCallback(() => {
    cancelHide();
    timer.current = window.setTimeout(hide, HIDE_DELAY);
  }, [cancelHide, hide]);

  const show = useCallback(() => {
    cancelHide();
    const el = tip.current;
    const anchor = button.current;
    // jsdom and older engines have no popover: the description still reaches a screen reader
    if (!el || !anchor || typeof el.showPopover !== "function") return;
    if (!el.matches(":popover-open")) el.showPopover();
    const field = anchor.closest(".ui-field") ?? anchor;
    const head = anchor.closest(".ui-field-head") ?? anchor;
    const box = field.getBoundingClientRect();
    const under = head.getBoundingClientRect().bottom + GAP;
    const height = el.offsetHeight;
    const top =
      under + height <= window.innerHeight
        ? under
        : Math.max(GAP, head.getBoundingClientRect().top - GAP - height);
    el.style.left = `${box.left}px`;
    el.style.top = `${top}px`;
    el.style.width = `${box.width}px`;
  }, [cancelHide]);

  // Placed once, where it opened: a scroll would leave it hanging over some other field
  useEffect(() => {
    document.addEventListener("scroll", hide, { capture: true, passive: true });
    return () => {
      document.removeEventListener("scroll", hide, { capture: true });
      cancelHide();
    };
  }, [hide, cancelHide]);

  return (
    <>
      <button
        ref={button}
        type="button"
        className="ui-tip-btn"
        aria-label={t("common.about", { topic })}
        aria-describedby={id}
        onMouseEnter={show}
        onMouseLeave={hideSoon}
        onFocus={show}
        onBlur={hide}
        onClick={show}
        onKeyDown={(e) => {
          if (e.key === "Escape") hide();
        }}
      >
        <Icon name="info" />
      </button>
      <div
        ref={tip}
        id={id}
        role="tooltip"
        popover="manual"
        className="ui-tip"
        onMouseEnter={cancelHide}
        onMouseLeave={hideSoon}
      >
        {children}
      </div>
    </>
  );
}
