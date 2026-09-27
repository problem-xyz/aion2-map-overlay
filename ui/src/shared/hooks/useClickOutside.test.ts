/**
 * Pins which events reach the handler, so the tests dispatch real events rather than calling it.
 *
 * Two properties carry the hook's purpose: a pointerdown inside the popover must never close it,
 * and the listener sits in the capture phase on purpose -- a child that stops propagation would
 * otherwise leave the popover open for good.
 */

import { act, renderHook } from "@testing-library/react";
import { createRef, type RefObject } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useClickOutside } from "./useClickOutside";

let ref: RefObject<HTMLDivElement | null>;
let node: HTMLDivElement;
let child: HTMLSpanElement;
let outside: HTMLDivElement;

beforeEach(() => {
  node = document.createElement("div");
  child = document.createElement("span");
  node.append(child);
  outside = document.createElement("div");
  document.body.append(node, outside);
  ref = createRef<HTMLDivElement>();
  ref.current = node;
});

afterEach(() => {
  node.remove();
  outside.remove();
});

function pointerDown(target: Element) {
  act(() => {
    target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
  });
}

describe("useClickOutside", () => {
  it("fires for a pointerdown outside the node", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside));

    pointerDown(outside);

    expect(onOutside).toHaveBeenCalledTimes(1);
  });

  it("stays silent for a pointerdown on the node itself", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside));

    pointerDown(node);

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("stays silent for a pointerdown on a descendant of the node", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside));

    pointerDown(child);

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("stays silent while the ref is empty", () => {
    const onOutside = vi.fn();
    ref.current = null;
    renderHook(() => useClickOutside(ref, onOutside));

    pointerDown(outside);

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("listens for pointerdown only, not mousedown or click", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside));

    act(() => {
      outside.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      outside.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("sees the event in the capture phase, so stopPropagation cannot hide it", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside));
    outside.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
    });

    pointerDown(outside);

    expect(onOutside).toHaveBeenCalledTimes(1);
  });

  it("does not listen while active is false", () => {
    const onOutside = vi.fn();
    renderHook(() => useClickOutside(ref, onOutside, false));

    pointerDown(outside);

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("stops listening when active turns false", () => {
    const onOutside = vi.fn();
    const { rerender } = renderHook(({ active }) => useClickOutside(ref, onOutside, active), {
      initialProps: { active: true },
    });

    pointerDown(outside);
    expect(onOutside).toHaveBeenCalledTimes(1);

    rerender({ active: false });
    pointerDown(outside);

    expect(onOutside).toHaveBeenCalledTimes(1);
  });

  it("starts listening again when active turns back on", () => {
    const onOutside = vi.fn();
    const { rerender } = renderHook(({ active }) => useClickOutside(ref, onOutside, active), {
      initialProps: { active: false },
    });

    rerender({ active: true });
    pointerDown(outside);

    expect(onOutside).toHaveBeenCalledTimes(1);
  });

  it("removes the listener on unmount", () => {
    const onOutside = vi.fn();
    const { unmount } = renderHook(() => useClickOutside(ref, onOutside));

    unmount();
    pointerDown(outside);

    expect(onOutside).not.toHaveBeenCalled();
  });

  it("calls the newest handler without re-registering the listener", () => {
    const first = vi.fn();
    const second = vi.fn();
    const add = vi.spyOn(document, "addEventListener");
    const { rerender } = renderHook(({ onOutside }) => useClickOutside(ref, onOutside), {
      initialProps: { onOutside: first },
    });
    const registrations = add.mock.calls.length;

    rerender({ onOutside: second });
    pointerDown(outside);

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    expect(add.mock.calls.length).toBe(registrations);

    add.mockRestore();
  });
});
