/**
 * What a page gets when it asks for an api instead of the raw Qt object.
 *
 * Two things are load-bearing and neither is visible from a component: the api is null until
 * there is an object to wrap, and it is the *same* api across re-renders -- a fresh wrapper each
 * render would make every callback closing over it a new reference and quietly undo the
 * memoisation below it. Outside a provider the hook has to fail loudly, not hand back nothing.
 *
 * A .ts file rather than .tsx: the provider is only ever needed as a renderHook wrapper, and
 * createElement expresses that without dragging JSX into a hook test.
 */

import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackendProvider } from "./BackendProvider";
import { useApi, useStepsApi } from "./hooks";
import { connectObject } from "./transport";

vi.mock("./transport", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./transport")>()),
  connectObject: vi.fn(),
}));

interface Channel {
  /** Resolve the connection, then let the provider's own chain finish before anything asserts. */
  ready: (object: Record<string, unknown>) => Promise<void>;
}

/** Hands the provider a connection this test decides the timing of. */
function channel(): Channel {
  let settle!: (object: Record<string, unknown>) => void;
  const promise = new Promise<Record<string, unknown>>((resolve) => {
    settle = resolve;
  });
  vi.mocked(connectObject).mockReturnValue(promise);
  return {
    ready: async (object) => {
      await act(async () => {
        settle(object);
        await promise;
      });
    },
  };
}

const signal = () => ({ connect: vi.fn(), disconnect: vi.fn() });

function fakeBackend() {
  return {
    stateChanged: signal(),
    getState: vi.fn((cb: (json: string) => void) => cb('{"version":"9.9.9"}')),
    setRoute: vi.fn(),
    updateSettings: vi.fn(),
  };
}

function fakeSteps() {
  return {
    dataChanged: signal(),
    getData: vi.fn((cb: (json: string) => void) => cb('{"title":"Altgard","done":2}')),
    action: vi.fn(),
    setHeight: vi.fn(),
  };
}

function backendWrapper(props: { children: ReactNode }) {
  return createElement(BackendProvider, props);
}

function stepsWrapper(props: { children: ReactNode }) {
  return createElement(BackendProvider, {
    ...props,
    object: "steps",
    stateSignal: "dataChanged",
    stateGetter: "getData",
  });
}

beforeEach(() => {
  vi.mocked(connectObject).mockReset();
});

describe("useApi", () => {
  it("is null while there is no object to wrap", () => {
    channel();

    const { result } = renderHook(() => useApi(), { wrapper: backendWrapper });

    expect(result.current).toBeNull();
  });

  it("wraps the object once the connection is ready, and keeps the same wrapper", async () => {
    const connection = channel();

    const { result, rerender } = renderHook(() => useApi(), { wrapper: backendWrapper });
    await connection.ready(fakeBackend());

    const api = result.current;
    expect(api).not.toBeNull();

    rerender();
    expect(result.current).toBe(api);
  });

  it("reaches the slots behind it, parsing what comes back", async () => {
    const connection = channel();
    const object = fakeBackend();

    const { result } = renderHook(() => useApi(), { wrapper: backendWrapper });
    await connection.ready(object);

    result.current?.setRoute("altgard-loop");
    expect(object.setRoute).toHaveBeenCalledWith("altgard-loop");

    const state = await result.current?.getState();
    expect(state?.version).toBe("9.9.9");
  });

  it("throws outside a provider rather than handing back nothing", () => {
    // React logs the render error before re-throwing it; the log is noise, not the assertion.
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useApi())).toThrow(/BackendProvider/);

    logged.mockRestore();
  });
});

describe("useStepsApi", () => {
  it("wraps the steps object, which has a different signal and getter", async () => {
    const connection = channel();
    const object = fakeSteps();

    const { result } = renderHook(() => useStepsApi(), { wrapper: stepsWrapper });
    expect(result.current).toBeNull();

    await connection.ready(object);

    expect(connectObject).toHaveBeenCalledWith("steps");

    result.current?.action("pin");
    expect(object.action).toHaveBeenCalledWith("pin");

    const data = await result.current?.getData();
    expect(data?.title).toBe("Altgard");
  });

  it("throws outside a provider rather than handing back nothing", () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useStepsApi())).toThrow(/BackendProvider/);

    logged.mockRestore();
  });
});
