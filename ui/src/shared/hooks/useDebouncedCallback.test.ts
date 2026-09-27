/**
 * Pins the contract stated in the hook's own docstring: trailing edge, at most one call per
 * window, the last arguments win, and nothing is dropped silently -- flush and unmount both send
 * the pending value, because a debounced call that never happens is a lost edit.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedCallback } from "./useDebouncedCallback";

const MS = 300;

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useDebouncedCallback", () => {
  it("does not fire on the leading edge", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    expect(fn).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(MS - 1);
    });

    expect(fn).not.toHaveBeenCalled();
  });

  it("fires once on the trailing edge", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => {
      vi.advanceTimersByTime(MS);
    });

    expect(fn.mock.calls).toEqual([[1]]);
  });

  it("collapses a burst into one call carrying the last arguments", () => {
    const fn = vi.fn<(value: number, label: string) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => {
      result.current(1, "a");
      vi.advanceTimersByTime(MS - 1);
      result.current(2, "b");
      vi.advanceTimersByTime(MS - 1);
      result.current(3, "c");
      vi.advanceTimersByTime(MS);
    });

    expect(fn.mock.calls).toEqual([[3, "c"]]);
  });

  it("opens a fresh window for a call made after the previous one fired", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => {
      vi.advanceTimersByTime(MS);
    });
    act(() => result.current(2));
    act(() => {
      vi.advanceTimersByTime(MS);
    });

    expect(fn.mock.calls).toEqual([[1], [2]]);
  });

  it("keeps one identity while fn changes, so a memoised child is not re-rendered", () => {
    const { result, rerender } = renderHook(({ fn }) => useDebouncedCallback(fn, MS), {
      initialProps: { fn: vi.fn<(value: number) => void>() },
    });
    const first = result.current;

    rerender({ fn: vi.fn<(value: number) => void>() });

    expect(result.current).toBe(first);
  });
});

describe("useDebouncedCallback: flush", () => {
  it("fires the pending call immediately", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(7));
    act(() => result.current.flush());

    expect(fn.mock.calls).toEqual([[7]]);
  });

  it("leaves nothing behind: no queued timer and no second call", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(7));
    act(() => result.current.flush());

    expect(vi.getTimerCount()).toBe(0);

    act(() => {
      vi.advanceTimersByTime(MS * 2);
    });

    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("does nothing when no call is pending", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current.flush());
    act(() => result.current.flush());

    expect(fn).not.toHaveBeenCalled();
  });

  it("starts from empty again, so the next call still debounces", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => result.current.flush());
    act(() => result.current(2));

    expect(fn).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(MS);
    });

    expect(fn.mock.calls).toEqual([[1], [2]]);
  });
});

describe("useDebouncedCallback: cancel", () => {
  it("drops the pending call", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => result.current.cancel());
    act(() => {
      vi.advanceTimersByTime(MS * 2);
    });

    expect(fn).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("leaves flush and unmount with nothing to fire", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result, unmount } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => result.current.cancel());
    act(() => result.current.flush());
    unmount();

    expect(fn).not.toHaveBeenCalled();
  });
});

describe("useDebouncedCallback: unmount", () => {
  it("flushes the pending call, because closing the window must not lose the last value", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result, unmount } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(42));
    expect(fn).not.toHaveBeenCalled();

    unmount();

    expect(fn.mock.calls).toEqual([[42]]);
  });

  it("flushes only what is still pending, not a call that already fired", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result, unmount } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(1));
    act(() => {
      vi.advanceTimersByTime(MS);
    });
    unmount();

    expect(fn.mock.calls).toEqual([[1]]);
  });

  it("fires nothing when no call is pending", () => {
    const fn = vi.fn<(value: number) => void>();
    const { unmount } = renderHook(() => useDebouncedCallback(fn, MS));

    unmount();

    expect(fn).not.toHaveBeenCalled();
  });

  it("does not fire a second time once the unmount flush has run", () => {
    const fn = vi.fn<(value: number) => void>();
    const { result, unmount } = renderHook(() => useDebouncedCallback(fn, MS));

    act(() => result.current(42));
    unmount();

    expect(vi.getTimerCount()).toBe(0);

    act(() => {
      vi.advanceTimersByTime(MS * 2);
    });

    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("useDebouncedCallback: a changing fn", () => {
  it("fires the newest fn, not the one captured when the call was made", () => {
    const first = vi.fn<(value: number) => void>();
    const second = vi.fn<(value: number) => void>();
    const { result, rerender } = renderHook(({ fn }) => useDebouncedCallback(fn, MS), {
      initialProps: { fn: first },
    });

    act(() => result.current(1));
    rerender({ fn: second });
    act(() => {
      vi.advanceTimersByTime(MS);
    });

    expect(first).not.toHaveBeenCalled();
    expect(second.mock.calls).toEqual([[1]]);
  });

  it("flushes through the newest fn", () => {
    const first = vi.fn<(value: number) => void>();
    const second = vi.fn<(value: number) => void>();
    const { result, rerender } = renderHook(({ fn }) => useDebouncedCallback(fn, MS), {
      initialProps: { fn: first },
    });

    act(() => result.current(1));
    rerender({ fn: second });
    act(() => result.current.flush());

    expect(first).not.toHaveBeenCalled();
    expect(second.mock.calls).toEqual([[1]]);
  });

  it("flushes through the newest fn on unmount", () => {
    const first = vi.fn<(value: number) => void>();
    const second = vi.fn<(value: number) => void>();
    const { result, rerender, unmount } = renderHook(({ fn }) => useDebouncedCallback(fn, MS), {
      initialProps: { fn: first },
    });

    act(() => result.current(1));
    rerender({ fn: second });
    unmount();

    expect(first).not.toHaveBeenCalled();
    expect(second.mock.calls).toEqual([[1]]);
  });
});
