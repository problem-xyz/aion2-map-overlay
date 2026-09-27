/**
 * What the toast queue promises: a toast lives for TOAST_MS, dismissing it early takes its timer
 * with it, and unmounting takes every pending timer with it -- the leak the provider's Map of
 * timers exists to prevent. The pending-timer count is read from the fake clock rather than from
 * the provider, so these stay assertions about behaviour and not about the Map.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TOAST_MS, ToastProvider, useToasts } from "./ToastProvider";

// Counting renders is how "nothing fires later for that toast" is observed: a stray timeout
// would call dismiss(), and dismiss() always hands setToasts a fresh array, so React re-renders
// even though the list looks unchanged.
let renders = 0;

function useCountedToasts() {
  renders += 1;
  return useToasts();
}

describe("ToastProvider", () => {
  beforeEach(() => {
    renders = 0;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps a toast for exactly TOAST_MS", () => {
    const view = renderHook(useCountedToasts, { wrapper: ToastProvider });

    act(() => {
      view.result.current.push({ level: "info", text: "saved" });
    });
    expect(view.result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(TOAST_MS - 1);
    });
    expect(view.result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(view.result.current.toasts).toHaveLength(0);
  });

  it("gives each toast its own timer, so an older one does not take a younger one with it", () => {
    const view = renderHook(useCountedToasts, { wrapper: ToastProvider });

    act(() => {
      view.result.current.push({ level: "info", text: "first" });
    });
    act(() => {
      vi.advanceTimersByTime(TOAST_MS / 2);
      view.result.current.push({ level: "info", text: "second" });
    });

    act(() => {
      vi.advanceTimersByTime(TOAST_MS / 2);
    });
    expect(view.result.current.toasts.map((t) => t.text)).toEqual(["second"]);

    act(() => {
      vi.advanceTimersByTime(TOAST_MS / 2);
    });
    expect(view.result.current.toasts).toHaveLength(0);
  });

  it("clears the timer of a toast dismissed early", () => {
    const view = renderHook(useCountedToasts, { wrapper: ToastProvider });

    act(() => {
      view.result.current.push({ level: "error", text: "boom" });
    });
    const [toast] = view.result.current.toasts;
    expect(toast).toBeDefined();
    expect(vi.getTimerCount()).toBe(1);

    act(() => {
      view.result.current.dismiss(toast!.id);
    });
    expect(view.result.current.toasts).toHaveLength(0);
    expect(vi.getTimerCount()).toBe(0);

    const settled = renders;
    act(() => {
      vi.advanceTimersByTime(TOAST_MS * 2);
    });
    expect(renders).toBe(settled);
  });

  it("clears every pending timer when it unmounts", () => {
    const view = renderHook(useCountedToasts, { wrapper: ToastProvider });

    act(() => {
      view.result.current.push({ level: "info", text: "a" });
      view.result.current.push({ level: "warning", text: "b" });
      view.result.current.push({ level: "error", text: "c" });
    });
    expect(vi.getTimerCount()).toBe(3);

    view.unmount();

    expect(vi.getTimerCount()).toBe(0);
  });

  it("gives every toast its own id, even several in one tick", () => {
    const view = renderHook(useCountedToasts, { wrapper: ToastProvider });

    act(() => {
      view.result.current.push({ level: "info", text: "a" });
      view.result.current.push({ level: "info", text: "b" });
      view.result.current.push({ level: "info", text: "c" });
    });

    const ids = view.result.current.toasts.map((t) => t.id);
    expect(new Set(ids).size).toBe(3);

    // The consequence of a collision: dismissing one would take its twins with it.
    act(() => {
      view.result.current.dismiss(ids[0]!);
    });
    expect(view.result.current.toasts.map((t) => t.text)).toEqual(["b", "c"]);
  });

  it("throws when a component asks for toasts outside the provider", () => {
    // React logs the render error itself; the assertion is the throw, not the console noise.
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      expect(() => renderHook(useCountedToasts)).toThrow(/ToastProvider/);
    } finally {
      logged.mockRestore();
    }
  });
});
