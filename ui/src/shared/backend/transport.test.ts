/**
 * Getting hold of the Python object, and calling a slot on it. What this pins: the promise stays
 * pending until QWebChannel hands the objects over, a slot that never calls back ends as an error
 * rather than as a promise nobody will ever settle, every failure arrives as a BackendError
 * carrying a stable code rather than as a throw into a console nobody is watching, and a page that
 * really is inside a QWebEngineView never reaches for the dev mock.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMockObject } from "@/dev/mockBackend";

import { BackendError, call, CALL_TIMEOUT_MS, connectObject } from "./transport";

interface Channel {
  objects: Record<string, unknown>;
}

/**
 * The QWebChannel constructor is the one thing a test cannot let run: it would talk to a
 * transport that does not exist. The stub records the call so a test can decide *when* the
 * channel answers, which is the whole point of the pending assertion below.
 */
const channel = vi.hoisted(() => ({
  calls: [] as Array<{ transport: unknown; onReady: (channel: Channel) => void }>,
  throwOnConstruct: null as Error | null,
}));

const QWebChannelStub = vi.fn((transport: unknown, onReady: (c: Channel) => void) => {
  if (channel.throwOnConstruct) throw channel.throwOnConstruct;
  channel.calls.push({ transport, onReady });
});

// `import.meta.env.DEV` is true under Vitest, so the dev-only fallback is live in every test
// that does not stub it off. Mocking the module keeps the real one out of the graph.
vi.mock("@/dev/mockBackend", () => ({
  createMockObject: vi.fn((name: string) => ({ mockFor: name })),
}));

/** Stands for `window.qt.webChannelTransport`; only its identity matters. */
const TRANSPORT = { id: "qt-transport" };

/** Waits a macrotask, which flushes every microtask a resolved promise could still be queued in. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/** What a QWebEngineView page has: the transport, and the qwebchannel.js Python injects. */
function insideQtWebEngine() {
  window.qt = { webChannelTransport: TRANSPORT };
  window.QWebChannel = QWebChannelStub;
}

beforeEach(() => {
  channel.calls.length = 0;
  channel.throwOnConstruct = null;
  delete window.qt;
  delete window.QWebChannel;
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  delete window.qt;
  delete window.QWebChannel;
});

/** A slot that takes the callback and sits on it, the way a wedged Python side would. */
function silentSlot(): { object: Record<string, unknown>; answer: (value: string) => void } {
  let callback: ((value: string) => void) | null = null;
  return {
    object: {
      getEditorRoute: (cb: (value: string) => void) => {
        callback = cb;
      },
    },
    answer: (value) => (callback as unknown as (v: string) => void)(value),
  };
}

describe("BackendError", () => {
  it("uses the code as the message when no message is given", () => {
    const error = new BackendError("backend.noTransport");

    expect(error.code).toBe("backend.noTransport");
    expect(error.message).toBe("backend.noTransport");
  });

  it("keeps the code separate from the message, and is still an Error", () => {
    const error = new BackendError("backend.noObject", "steps");

    expect(error.code).toBe("backend.noObject");
    expect(error.message).toBe("steps");
    expect(error.name).toBe("BackendError");
    expect(error).toBeInstanceOf(Error);
  });
});

describe("connectObject", () => {
  it("loads the dev mock when the page asks for it with ?mock=1", async () => {
    insideQtWebEngine();
    window.history.replaceState({}, "", "/?mock=1");

    await expect(connectObject("steps")).resolves.toEqual({ mockFor: "steps" });
    expect(vi.mocked(createMockObject)).toHaveBeenCalledWith("steps");
  });

  it("leaves the mock alone for ?mock=0, which is the value and not the parameter talking", async () => {
    insideQtWebEngine();
    window.history.replaceState({}, "", "/?mock=0");

    const promise = connectObject<{ tag: string }>("backend");
    channel.calls[0]?.onReady({ objects: { backend: { tag: "real" } } });

    await expect(promise).resolves.toEqual({ tag: "real" });
    expect(vi.mocked(createMockObject)).not.toHaveBeenCalled();
  });

  it("falls back to the dev mock in a dev build when there is no Qt at all", async () => {
    await expect(connectObject("backend")).resolves.toEqual({ mockFor: "backend" });
  });

  it("never reaches for the mock when the page is inside a QWebEngineView", async () => {
    insideQtWebEngine();

    const promise = connectObject<{ tag: string }>("backend");
    channel.calls[0]?.onReady({ objects: { backend: { tag: "real" } } });

    await expect(promise).resolves.toEqual({ tag: "real" });
    expect(vi.mocked(createMockObject)).not.toHaveBeenCalled();
  });

  it("fails with backend.noTransport when a production build is opened in a browser", async () => {
    vi.stubEnv("DEV", false);

    await expect(connectObject("backend")).rejects.toMatchObject({
      name: "BackendError",
      code: "backend.noTransport",
    });
    expect(channel.calls).toHaveLength(0);
  });

  it("fails with backend.noTransport when window.qt exists but carries no transport", async () => {
    window.qt = {};

    await expect(connectObject("backend")).rejects.toMatchObject({
      code: "backend.noTransport",
    });
  });

  it("hands the Qt transport to QWebChannel and resolves with the named object", async () => {
    insideQtWebEngine();
    const backend = { tag: "backend" };
    const steps = { tag: "steps" };

    const promise = connectObject<{ tag: string }>("steps");

    expect(channel.calls[0]?.transport).toBe(TRANSPORT);
    channel.calls[0]?.onReady({ objects: { backend, steps } });
    await expect(promise).resolves.toBe(steps);
  });

  it("stays pending until the channel calls back", async () => {
    insideQtWebEngine();
    let settled = false;

    const promise = connectObject("backend").then(
      (value) => {
        settled = true;
        return value;
      },
      () => {
        settled = true;
      },
    );
    await flush();

    expect(settled).toBe(false);

    channel.calls[0]?.onReady({ objects: { backend: { tag: "real" } } });
    await promise;
    expect(settled).toBe(true);
  });

  it("rejects with backend.noObject, naming the object, when the channel has no such name", async () => {
    insideQtWebEngine();

    const promise = connectObject("steps");
    channel.calls[0]?.onReady({ objects: { backend: {} } });

    await expect(promise).rejects.toMatchObject({
      code: "backend.noObject",
      message: "steps",
    });
  });

  it("rejects with backend.channelFailed when constructing the channel throws", async () => {
    insideQtWebEngine();
    channel.throwOnConstruct = new Error("transport is closed");

    await expect(connectObject("backend")).rejects.toMatchObject({
      code: "backend.channelFailed",
      message: expect.stringContaining("transport is closed") as unknown as string,
    });
  });

  it("rejects with backend.channelFailed when the page has a transport but no qwebchannel.js", async () => {
    insideQtWebEngine();
    delete window.QWebChannel;

    await expect(connectObject("backend")).rejects.toMatchObject({
      code: "backend.channelFailed",
    });
  });
});

describe("call", () => {
  it("resolves with whatever the slot hands to its trailing callback", async () => {
    const object = { getState: (cb: (json: string) => void) => cb('{"running":true}') };

    await expect(call<string>(object, "getState")).resolves.toBe('{"running":true}');
  });

  it("passes the arguments in order and appends the callback last", async () => {
    const seen: unknown[] = [];
    const object = {
      setHotspot: (...args: unknown[]) => {
        seen.push(...args);
        (args[args.length - 1] as (v: string) => void)("done");
      },
    };

    await expect(call<string>(object, "setHotspot", 1, 2, 3, 4)).resolves.toBe("done");
    expect(seen.slice(0, 4)).toEqual([1, 2, 3, 4]);
    expect(typeof seen[4]).toBe("function");
    expect(seen).toHaveLength(5);
  });

  it("calls the slot with the object as its receiver", async () => {
    // Qt's generated slots read state off the object they hang on, so losing `this` here would
    // only show up inside a QWebEngineView, where there is no console to see it in.
    const object = {
      name: "backend",
      getName(this: { name: string }, cb: (value: string) => void) {
        cb(this.name);
      },
    };

    await expect(call<string>(object, "getName")).resolves.toBe("backend");
  });

  it("rejects with backend.noSlot, naming the method, when the object has no such slot", async () => {
    await expect(call({}, "getState")).rejects.toMatchObject({
      name: "BackendError",
      code: "backend.noSlot",
      message: "getState",
    });
  });

  it("rejects with backend.noSlot when the property exists but is not callable", async () => {
    await expect(call({ getState: "not a slot" }, "getState")).rejects.toMatchObject({
      code: "backend.noSlot",
    });
  });

  it("rejects with backend.noSlot instead of throwing when there is no object at all", async () => {
    await expect(call(null, "getState")).rejects.toMatchObject({ code: "backend.noSlot" });
    await expect(call(undefined, "getState")).rejects.toMatchObject({ code: "backend.noSlot" });
  });

  it("rejects rather than letting an exception from the slot escape the promise", async () => {
    vi.useFakeTimers();
    const object = {
      start: () => {
        throw new Error("channel is gone");
      },
    };

    await expect(call(object, "start")).rejects.toThrow("channel is gone");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stays pending while the slot has not answered, right up to the timeout", async () => {
    vi.useFakeTimers();
    const slot = silentSlot();
    let settled = false;

    const promise = call<string>(slot.object, "getEditorRoute").then((value) => {
      settled = true;
      return value;
    });
    await vi.advanceTimersByTimeAsync(CALL_TIMEOUT_MS - 1);

    expect(settled).toBe(false);

    slot.answer("altgard");
    await expect(promise).resolves.toBe("altgard");
    // The timer goes with the answer: left armed, it would reject a promise already resolved.
    expect(vi.getTimerCount()).toBe(0);
  });

  it("rejects with backend.slotTimeout, naming the method, when the slot never answers", async () => {
    vi.useFakeTimers();
    const slot = silentSlot();

    const settled = expect(call(slot.object, "getEditorRoute")).rejects.toMatchObject({
      name: "BackendError",
      code: "backend.slotTimeout",
      message: "getEditorRoute",
    });
    await vi.advanceTimersByTimeAsync(CALL_TIMEOUT_MS);

    await settled;
  });

  it("gives the slot the whole timeout and not a moment less", async () => {
    vi.useFakeTimers();
    const slot = silentSlot();
    let settled = false;

    void call(slot.object, "getEditorRoute").catch(() => {
      settled = true;
    });
    await vi.advanceTimersByTimeAsync(CALL_TIMEOUT_MS - 1);

    expect(settled).toBe(false);
  });
});
