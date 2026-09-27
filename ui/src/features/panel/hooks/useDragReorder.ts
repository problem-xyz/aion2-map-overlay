import { type CSSProperties, type PointerEvent, useEffect, useRef, useState } from "react";

/** How far the pointer travels before a press on a row becomes a drag rather than a click. */
const THRESHOLD = 5;
/** The band at the scroller's top and bottom edge that scrolls it while a row is held there. */
const EDGE = 36;
/** The most the scroller moves in a frame, reached at its very edge. */
const MAX_SPEED = 14;

interface Drag {
  from: number;
  to: number;
  dy: number;
  /** One row's height and the gap under it: how far a row steps aside. */
  step: number;
}

interface Press {
  index: number;
  count: number;
  pointerId: number;
  y: number;
  lastY: number;
  el: HTMLElement;
  scroller: Element;
  scroll0: number;
  step: number;
  drag: Drag | null;
  frame: number;
  stop: () => void;
}

/** `items` with the one at `from` taken out and put back at `to`. */
export function moved<T>(items: readonly T[], from: number, to: number): T[] {
  const out = [...items];
  const [item] = out.splice(from, 1);
  if (item !== undefined) out.splice(to, 0, item);
  return out;
}

function scrollerOf(el: Element): Element {
  for (let at = el.parentElement; at; at = at.parentElement) {
    const { overflowY } = getComputedStyle(at);
    if ((overflowY === "auto" || overflowY === "scroll") && at.scrollHeight > at.clientHeight) {
      return at;
    }
  }
  return document.scrollingElement ?? document.documentElement;
}

function edgesOf(scroller: Element): { top: number; bottom: number } {
  if (scroller === document.scrollingElement) return { top: 0, bottom: window.innerHeight };
  const r = scroller.getBoundingClientRect();
  return { top: r.top, bottom: r.bottom };
}

function swallowClick(e: MouseEvent) {
  e.stopPropagation();
  e.preventDefault();
}

/**
 * A list reordered by dragging its rows. The held row follows the pointer, the rows it passes
 * step aside, and the list scrolls while the row is held at its edge; on release `onReorder`
 * gets the list with the row moved. The rows are taken to be one height, as tiles are.
 *
 * A press that does not travel THRESHOLD pixels is left alone, so the row's click still
 * selects it. One that does is a drag, and the click the browser sends after it is swallowed.
 * An element marked `data-no-drag` inside a row (its own buttons) never starts one.
 */
export function useDragReorder(count: number, onReorder: (from: number, to: number) => void) {
  const [drag, setDrag] = useState<Drag | null>(null);
  // The frame a drop lands in. The rows are put in their new order and lose their offsets in
  // one render; a transition then would slide each from its offset measured from the old place.
  const [settling, setSettling] = useState(false);
  const press = useRef<Press | null>(null);
  const reorder = useRef(onReorder);
  useEffect(() => {
    reorder.current = onReorder;
  });
  useEffect(() => () => press.current?.stop(), []);

  function onPointerDown(e: PointerEvent<HTMLElement>, index: number) {
    if (e.button !== 0 || press.current) return;
    if ((e.target as Element).closest("[data-no-drag]")) return;
    const el = e.currentTarget;
    const list = el.parentElement;
    const gap = list ? parseFloat(getComputedStyle(list).rowGap) || 0 : 0;
    const scroller = scrollerOf(el);

    const follow = (p: Press) => {
      const dy = p.lastY - p.y + (p.scroller.scrollTop - p.scroll0);
      if (!p.drag && Math.abs(dy) < THRESHOLD) return;
      if (!p.drag) {
        // Capture keeps the click that ends the drag off the row's button. It throws for a
        // pointer that is already gone; the drag goes on without it, and the click is swallowed.
        try {
          el.setPointerCapture(p.pointerId);
        } catch {
          /* released before the drag started */
        }
        p.frame = requestAnimationFrame(tick);
      }
      const to = Math.min(p.count - 1, Math.max(0, p.index + Math.round(dy / p.step)));
      p.drag = { from: p.index, to, dy, step: p.step };
      setDrag(p.drag);
    };
    const tick = () => {
      const p = press.current;
      if (!p) return;
      const { top, bottom } = edgesOf(p.scroller);
      const into =
        p.lastY < top + EDGE
          ? p.lastY - top - EDGE
          : p.lastY > bottom - EDGE
            ? p.lastY - bottom + EDGE
            : 0;
      if (into !== 0) {
        p.scroller.scrollTop += Math.max(-MAX_SPEED, Math.min(MAX_SPEED, into / 2));
        follow(p);
      }
      p.frame = requestAnimationFrame(tick);
    };
    const end = (commit: boolean) => {
      const p = press.current;
      if (!p) return;
      p.stop();
      if (!p.drag) return;
      // The click that follows a drag must not select the row it was dropped on. It is not
      // always sent -- the pointer may be released outside the window -- so the listener goes
      // once this input event is over either way.
      window.addEventListener("click", swallowClick, { capture: true, once: true });
      setTimeout(() => window.removeEventListener("click", swallowClick, { capture: true }), 0);
      const { from, to } = p.drag;
      setDrag(null);
      if (commit && to !== from) {
        setSettling(true);
        requestAnimationFrame(() => requestAnimationFrame(() => setSettling(false)));
        reorder.current(from, to);
      }
    };
    const onMove = (ev: globalThis.PointerEvent) => {
      const p = press.current;
      if (!p || ev.pointerId !== p.pointerId) return;
      p.lastY = ev.clientY;
      follow(p);
    };
    const onUp = (ev: globalThis.PointerEvent) => {
      if (ev.pointerId === press.current?.pointerId) end(true);
    };
    const onCancel = (ev: globalThis.PointerEvent) => {
      if (ev.pointerId === press.current?.pointerId) end(false);
    };
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") end(false);
    };

    press.current = {
      index,
      count,
      pointerId: e.pointerId,
      y: e.clientY,
      lastY: e.clientY,
      el,
      scroller,
      scroll0: scroller.scrollTop,
      step: Math.max(1, el.offsetHeight + gap),
      drag: null,
      frame: 0,
      stop: () => {
        const p = press.current;
        press.current = null;
        if (p) cancelAnimationFrame(p.frame);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onCancel);
        window.removeEventListener("keydown", onKey);
        setDrag(null);
      },
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    window.addEventListener("keydown", onKey);
  }

  /** Where row `index` is drawn while a drag is on: the held row under the pointer, each row
   *  it has passed one step towards the gap it left. */
  function styleOf(index: number): CSSProperties | undefined {
    if (settling) return { transition: "none" };
    if (!drag) return undefined;
    const { from, to, dy, step } = drag;
    if (index === from) return { transform: `translateY(${dy}px)` };
    if (from < to && index > from && index <= to) return { transform: `translateY(${-step}px)` };
    if (to < from && index >= to && index < from) return { transform: `translateY(${step}px)` };
    return undefined;
  }

  return { dragging: drag?.from ?? null, onPointerDown, styleOf };
}
