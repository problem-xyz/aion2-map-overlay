/**
 * Pins useLatest: one ref object for the lifetime of the component, refreshed after every commit.
 *
 * A long-lived subscription captures this ref once and keeps calling through it. A new ref per
 * render, or a value that stops being refreshed, would leave that subscription on a stale handler.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useLatest } from "./useLatest";

describe("useLatest", () => {
  it("holds the initial value", () => {
    const { result } = renderHook(() => useLatest("a"));

    expect(result.current.current).toBe("a");
  });

  it("holds the newest value after a rerender", () => {
    const { result, rerender } = renderHook(({ value }) => useLatest(value), {
      initialProps: { value: "a" },
    });

    rerender({ value: "b" });

    expect(result.current.current).toBe("b");
  });

  it("keeps the same ref object across rerenders", () => {
    const { result, rerender } = renderHook(({ value }) => useLatest(value), {
      initialProps: { value: 1 },
    });
    const ref = result.current;

    rerender({ value: 2 });
    rerender({ value: 3 });

    expect(result.current).toBe(ref);
    expect(ref.current).toBe(3);
  });

  it("carries a callback, so a caller reaching through the ref runs the newest one", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { result, rerender } = renderHook(({ fn }) => useLatest(fn), {
      initialProps: { fn: first },
    });

    rerender({ fn: second });
    result.current.current();

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("keeps null and undefined rather than treating them as no value", () => {
    const initialProps: { value: string | null | undefined } = { value: "a" };
    const { result, rerender } = renderHook(({ value }) => useLatest(value), { initialProps });

    rerender({ value: null });
    expect(result.current.current).toBeNull();

    rerender({ value: undefined });
    expect(result.current.current).toBeUndefined();
  });

  it("writes in an effect, so a read during render still sees the previous value", () => {
    const seen: number[] = [];
    const { result, rerender } = renderHook(
      ({ value }) => {
        const ref = useLatest(value);
        seen.push(ref.current);
        return ref;
      },
      { initialProps: { value: 1 } },
    );

    rerender({ value: 2 });

    expect(seen).toEqual([1, 1]);
    expect(result.current.current).toBe(2);
  });
});
