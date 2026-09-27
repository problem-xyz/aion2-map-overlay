/**
 * The store every subscriber in the UI hangs off. Two properties carry the weight: a set that
 * resolves to the value already held must notify nobody -- stats arrive at 15 Hz and each
 * notification is a render -- and the value must be replaced, never merged into, because
 * useSyncExternalStore decides whether to re-render by comparing identity.
 */

import { describe, expect, it, vi } from "vitest";

import { createStore } from "./store";

describe("createStore", () => {
  it("hands back the initial value before anything sets it", () => {
    expect(createStore(7).get()).toBe(7);
    expect(createStore<string | null>(null).get()).toBeNull();
  });

  it("replaces the value and tells every subscriber", () => {
    const store = createStore(1);
    const first = vi.fn();
    const second = vi.fn();
    store.subscribe(first);
    store.subscribe(second);

    store.set(2);

    expect(store.get()).toBe(2);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("passes the current value to an updater function and stores what it returns", () => {
    const store = createStore({ done: 1 });
    const seen: number[] = [];

    store.set((prev) => {
      seen.push(prev.done);
      return { done: prev.done + 1 };
    });
    store.set((prev) => ({ done: prev.done + 1 }));

    expect(seen).toEqual([1]);
    expect(store.get()).toEqual({ done: 3 });
  });

  it("stores the object it is handed instead of merging it into the old one", () => {
    const initial = { running: false, route: "altgard" };
    const store = createStore(initial);
    const next = { running: true, route: "beluslan" };

    store.set(next);

    expect(store.get()).toBe(next);
    expect(initial).toEqual({ running: false, route: "altgard" });
  });

  it("has the new value in place before any listener runs", () => {
    const store = createStore(1);
    const seen: number[] = [];
    store.subscribe(() => seen.push(store.get()));

    store.set(2);

    expect(seen).toEqual([2]);
  });

  it("notifies nobody when the set resolves to the value already held", () => {
    const held = { fps: 60 };
    const store = createStore(held);
    const listener = vi.fn();
    store.subscribe(listener);

    store.set(held);
    store.set(() => held);

    expect(listener).not.toHaveBeenCalled();
  });

  it("still notifies for an equal but distinct object, because identity is what is compared", () => {
    const store = createStore({ fps: 60 });
    const listener = vi.fn();
    store.subscribe(listener);

    store.set({ fps: 60 });

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("compares with Object.is, so NaN counts as unchanged and -0 does not", () => {
    const nan = createStore(Number.NaN);
    const nanListener = vi.fn();
    nan.subscribe(nanListener);
    nan.set(Number.NaN);

    const zero = createStore(0);
    const zeroListener = vi.fn();
    zero.subscribe(zeroListener);
    zero.set(-0);

    expect(nanListener).not.toHaveBeenCalled();
    expect(zeroListener).toHaveBeenCalledTimes(1);
  });

  it("stops notifying a listener once its unsubscribe has run", () => {
    const store = createStore(0);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    store.set(1);
    unsubscribe();
    store.set(2);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(store.get()).toBe(2);
  });

  it("keeps the other subscribers when one of them unsubscribes", () => {
    const store = createStore(0);
    const staying = vi.fn();
    const leaving = vi.fn();
    store.subscribe(staying);
    const unsubscribe = store.subscribe(leaving);

    unsubscribe();
    store.set(1);

    expect(staying).toHaveBeenCalledTimes(1);
    expect(leaving).not.toHaveBeenCalled();
  });

  it("survives a second unsubscribe from the same subscription", () => {
    const store = createStore(0);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    unsubscribe();

    expect(() => unsubscribe()).not.toThrow();
    store.set(1);
    expect(listener).not.toHaveBeenCalled();
  });

  it("notifies a listener registered twice only once per change", () => {
    const store = createStore(0);
    const listener = vi.fn();
    store.subscribe(listener);
    store.subscribe(listener);

    store.set(1);

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps two stores apart", () => {
    const first = createStore(1);
    const second = createStore(1);
    const listener = vi.fn();
    second.subscribe(listener);

    first.set(2);

    expect(second.get()).toBe(1);
    expect(listener).not.toHaveBeenCalled();
  });
});
