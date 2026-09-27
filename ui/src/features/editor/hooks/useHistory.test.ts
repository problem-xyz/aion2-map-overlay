import { act, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";

import useHistory, { HISTORY_LIMIT } from "./useHistory";

describe("useHistory: set", () => {
  it("pushes the previous value onto the past", () => {
    const first = [1];
    const second = [1, 2];
    const { result } = renderHook(() => useHistory<number>(first));

    act(() => {
      result.current.set(second);
    });

    expect(result.current.items).toBe(second);
    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.items).toBe(first);
  });

  it("accepts an updater called with the current items", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set((prev) => [...prev, 2]);
    });

    expect(result.current.items).toEqual([1, 2]);
    expect(result.current.canUndo).toBe(true);
  });

  it("clears the future so a redo is no longer offered", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set([1, 2]);
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.set([9]);
    });

    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.redo();
    });

    expect(result.current.items).toEqual([9]);
  });

  it("records nothing when the value is the identical reference", () => {
    const initial = [1];
    const { result } = renderHook(() => useHistory<number>(initial));

    act(() => {
      result.current.set(initial);
    });

    expect(result.current.canUndo).toBe(false);

    act(() => {
      result.current.set((prev) => prev);
    });

    expect(result.current.canUndo).toBe(false);
    expect(result.current.items).toBe(initial);
  });
});

describe("useHistory: setTransient", () => {
  it("changes the items without recording history", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.setTransient([1, 2]);
      result.current.setTransient((prev) => [...prev, 3]);
    });

    expect(result.current.items).toEqual([1, 2, 3]);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it("leaves an existing future untouched", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set([1, 2]);
      result.current.undo();
      result.current.setTransient([7]);
    });

    expect(result.current.items).toEqual([7]);
    expect(result.current.canRedo).toBe(true);
  });
});

describe("useHistory: begin/end", () => {
  it("records one entry for a whole run of transient changes", () => {
    const initial = [1];
    const { result } = renderHook(() => useHistory<number>(initial));

    act(() => {
      result.current.begin();
      result.current.setTransient([1, 2]);
      result.current.setTransient([1, 2, 3]);
      result.current.setTransient([1, 2, 3, 4]);
      result.current.end();
    });

    expect(result.current.items).toEqual([1, 2, 3, 4]);
    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.items).toBe(initial);
    expect(result.current.canUndo).toBe(false);
  });

  it("drops the future when the edit is committed", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set([1, 2]);
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.begin();
      result.current.setTransient([5]);
      result.current.end();
    });

    expect(result.current.canRedo).toBe(false);
  });

  it("records nothing on an end without a begin", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.setTransient([1, 2]);
      result.current.end();
    });

    expect(result.current.items).toEqual([1, 2]);
    expect(result.current.canUndo).toBe(false);
  });

  it("records nothing when the value did not change between begin and end", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.begin();
      result.current.end();
    });

    expect(result.current.canUndo).toBe(false);
  });
});

describe("useHistory: undo/redo", () => {
  it("restores the very same array reference on undo then redo", () => {
    const first = [1];
    const second = [1, 2];
    const { result } = renderHook(() => useHistory<number>(first));

    act(() => {
      result.current.set(second);
    });

    act(() => {
      result.current.undo();
    });

    expect(result.current.items).toBe(first);

    act(() => {
      result.current.redo();
    });

    expect(result.current.items).toBe(second);
  });

  it("walks back and forward through several steps in order", () => {
    const { result } = renderHook(() => useHistory<number>([0]));

    act(() => {
      result.current.set([1]);
      result.current.set([2]);
      result.current.set([3]);
    });

    act(() => {
      result.current.undo();
      result.current.undo();
    });

    expect(result.current.items).toEqual([1]);

    act(() => {
      result.current.redo();
    });

    expect(result.current.items).toEqual([2]);
  });

  it("is a no-op when the past is empty", () => {
    const initial = [1];
    const { result } = renderHook(() => useHistory<number>(initial));
    const before = result.current.items;

    act(() => {
      result.current.undo();
    });

    expect(result.current.items).toBe(before);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it("is a no-op when the future is empty", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set([1, 2]);
    });

    const before = result.current.items;

    act(() => {
      result.current.redo();
    });

    expect(result.current.items).toBe(before);
    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  it("reports canUndo and canRedo from the two stacks", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.set([1, 2]);
    });

    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.undo();
    });

    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.redo();
    });

    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });
});

describe("useHistory: reset", () => {
  it("installs the value and empties both stacks", () => {
    const fresh = [9];
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.set([1, 2]);
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.reset(fresh);
    });

    expect(result.current.items).toBe(fresh);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });

  it("drops an edit that was still open", () => {
    const { result } = renderHook(() => useHistory<number>([1]));

    act(() => {
      result.current.begin();
      result.current.reset([9]);
      result.current.end();
    });

    expect(result.current.items).toEqual([9]);
    expect(result.current.canUndo).toBe(false);
  });
});

describe("useHistory: HISTORY_LIMIT", () => {
  const extra = 5;

  it("keeps the newest HISTORY_LIMIT entries and drops the oldest", () => {
    const { result } = renderHook(() => useHistory<number>([0]));

    act(() => {
      for (let i = 1; i <= HISTORY_LIMIT + extra; i += 1) result.current.set([i]);
    });

    expect(result.current.items).toEqual([HISTORY_LIMIT + extra]);

    act(() => {
      for (let i = 0; i < HISTORY_LIMIT - 1; i += 1) result.current.undo();
    });

    // One entry short of the cap: the oldest surviving value is still one undo away.
    expect(result.current.items).toEqual([extra + 1]);
    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.items).toEqual([extra]);
    expect(result.current.canUndo).toBe(false);
  });
});

describe("useHistory under StrictMode", () => {
  // React double-invokes state updaters in development to surface impure ones. begin/end used to
  // do their bookkeeping inside the updater, so the second invocation saw an already-cleared
  // snapshot and threw the whole edit away: a drag could not be undone, and neither could a
  // caption. main.jsx wraps the app in StrictMode, so this is the mode the editor actually runs
  // in while it is being worked on.
  it("records one entry for a begin/setTransient/end edit", () => {
    const { result } = renderHook(() => useHistory<number>([1]), { wrapper: StrictMode });

    act(() => {
      result.current.begin();
      result.current.setTransient([1, 2]);
      result.current.end();
    });

    expect(result.current.items).toEqual([1, 2]);
    expect(result.current.canUndo).toBe(true);

    act(() => result.current.undo());

    expect(result.current.items).toEqual([1]);
    expect(result.current.canRedo).toBe(true);
  });

  it("still records nothing when the edit changed nothing", () => {
    const initial = [1];
    const { result } = renderHook(() => useHistory<number>(initial), { wrapper: StrictMode });

    act(() => {
      result.current.begin();
      result.current.end();
    });

    expect(result.current.canUndo).toBe(false);
  });

  it("records a plain set exactly once", () => {
    const { result } = renderHook(() => useHistory<number>([1]), { wrapper: StrictMode });

    act(() => result.current.set([1, 2]));
    act(() => result.current.undo());

    expect(result.current.items).toEqual([1]);
    expect(result.current.canUndo).toBe(false);
  });
});
