/**
 * What the provider owes the tree below it.
 *
 * Three things nothing else in the app checks: a consumer never sees a "ready" backend whose
 * state has not landed yet, a Qt signal reaches the store, and the signal is handed back on
 * unmount -- the leak this provider exists to prevent, so it is pinned by the disconnect call
 * and not by the absence of a crash.
 */

import { act, render, screen } from "@testing-library/react";
import { useEffect, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import {
  BackendProvider,
  useBackend,
  useBackendSignal,
  useBackendState,
  useBackendStore,
} from "./BackendProvider";
import type { Store } from "./store";
import { BackendError, connectObject } from "./transport";

// Only the connection is replaced. BackendError stays the real class, or `instanceof` stops
// meaning anything here and in BackendGate.
vi.mock("./transport", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./transport")>()),
  connectObject: vi.fn(),
}));

type Handler = (...args: unknown[]) => void;

interface FakeSignal {
  connect: Mock<(handler: Handler) => void>;
  disconnect: Mock<(handler: Handler) => void>;
  emit: (payload: string) => void;
}

function fakeSignal(): FakeSignal {
  const handlers = new Set<Handler>();
  return {
    connect: vi.fn((handler: Handler) => void handlers.add(handler)),
    disconnect: vi.fn((handler: Handler) => void handlers.delete(handler)),
    emit: (payload: string) => [...handlers].forEach((handler) => handler(payload)),
  };
}

interface FakeState {
  version: string;
}

interface Fake {
  object: Record<string, unknown>;
  state: FakeSignal;
  notify: FakeSignal;
  getter: Mock<(cb: (json: string) => void) => void>;
}

/**
 * A stand-in for a Qt object: slots are plain functions, signals are {connect, disconnect}.
 *
 * src/dev/mockBackend is not reused: it boots a module-level singleton that leaks between tests,
 * it starts a stats interval, and it answers every getter synchronously -- while what these
 * tests need is a fresh object each time and control over *when* the state arrives.
 */
function fake(options: { signal?: string; getter?: string; version?: string } = {}): Fake {
  const signalName = options.signal ?? "stateChanged";
  const getterName = options.getter ?? "getState";
  const state = fakeSignal();
  const notify = fakeSignal();
  // The getter answers a microtask later, like a real call across the channel. A callback that
  // fired synchronously would hide a provider that announces "ready" before the state is in.
  const getter = vi.fn((cb: (json: string) => void) => {
    void Promise.resolve().then(() => cb(JSON.stringify({ version: options.version ?? "1.0.0" })));
  });
  return { object: { [signalName]: state, [getterName]: getter, notify }, state, notify, getter };
}

interface Channel {
  /** Resolve the connection, then let the provider's own chain finish before anything asserts. */
  ready: (object: Record<string, unknown>) => Promise<void>;
  fail: (reason: unknown) => Promise<void>;
}

/** Hands the provider a connection this test decides the timing of. */
function channelOf(): Channel {
  let settle!: (object: Record<string, unknown>) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<Record<string, unknown>>((resolve, fail) => {
    settle = resolve;
    reject = fail;
  });
  vi.mocked(connectObject).mockReturnValue(promise);
  return {
    ready: async (object) => {
      await act(async () => {
        settle(object);
        await promise;
      });
    },
    fail: async (reason) => {
      await act(async () => {
        reject(reason);
        await promise.catch(() => undefined);
      });
    },
  };
}

/**
 * Records one line per *commit*, not per render call: what is asserted is what a user could have
 * been shown, and an effect with no dependency array runs exactly once per commit.
 */
function Probe({ commits = [] }: { commits?: string[] }) {
  const { status, error, object } = useBackend();
  const version = useBackendState<FakeState, string | null>((state) => state?.version ?? null);
  const line = `${status}/${object ? "object" : "none"}/${version ?? "none"}`;
  useEffect(() => {
    commits.push(line);
  });
  return (
    <>
      <span data-testid="probe">{line}</span>
      <span data-testid="error">{error instanceof BackendError ? error.code : "none"}</span>
    </>
  );
}

function text(id: string): string | null {
  return screen.getByTestId(id).textContent;
}

beforeEach(() => {
  vi.mocked(connectObject).mockReset();
});

describe("BackendProvider", () => {
  it("stays connecting until the channel resolves, then goes ready", async () => {
    const channel = channelOf();
    const target = fake({ version: "2.0.0" });

    render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    expect(text("probe")).toBe("connecting/none/none");
    expect(connectObject).toHaveBeenCalledWith("backend");

    await channel.ready(target.object);
    expect(text("probe")).toBe("ready/object/2.0.0");
  });

  it("never shows a ready backend without the state behind it", async () => {
    const channel = channelOf();
    const target = fake({ version: "2.0.0" });
    const commits: string[] = [];

    render(
      <BackendProvider>
        <Probe commits={commits} />
      </BackendProvider>,
    );
    await channel.ready(target.object);

    expect(commits.length).toBeGreaterThan(1);
    expect(commits.filter((line) => line.startsWith("ready"))).toEqual(["ready/object/2.0.0"]);
  });

  it("reports a failed connection as an error status, keeping the code", async () => {
    const channel = channelOf();

    render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    await channel.fail(new BackendError("backend.noTransport"));

    expect(text("probe")).toBe("error/none/none");
    expect(text("error")).toBe("backend.noTransport");
  });

  it("writes a signal payload into the store and re-renders the consumer", async () => {
    const channel = channelOf();
    const target = fake({ version: "1.0.0" });

    render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    await channel.ready(target.object);
    expect(text("probe")).toBe("ready/object/1.0.0");

    act(() => {
      target.state.emit(JSON.stringify({ version: "9.9.9" }));
    });
    expect(text("probe")).toBe("ready/object/9.9.9");
  });

  it("hands the state signal back on unmount", async () => {
    const channel = channelOf();
    const target = fake();

    const { unmount } = render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    await channel.ready(target.object);

    const handler = target.state.connect.mock.calls[0]?.[0];
    expect(typeof handler).toBe("function");
    expect(target.state.disconnect).not.toHaveBeenCalled();

    unmount();
    expect(target.state.disconnect).toHaveBeenCalledWith(handler);
  });

  it("ignores a channel that resolves after unmount", async () => {
    const channel = channelOf();
    const target = fake();

    const { unmount } = render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    unmount();
    await channel.ready(target.object);

    expect(target.state.connect).not.toHaveBeenCalled();
    expect(target.getter).not.toHaveBeenCalled();
  });

  it("uses the object, signal and getter it was given", async () => {
    const channel = channelOf();
    const target = fake({ signal: "dataChanged", getter: "getData", version: "steps" });

    const { unmount } = render(
      <BackendProvider object="steps" stateSignal="dataChanged" stateGetter="getData">
        <Probe />
      </BackendProvider>,
    );
    await channel.ready(target.object);

    expect(connectObject).toHaveBeenCalledWith("steps");
    expect(target.getter).toHaveBeenCalledTimes(1);
    expect(text("probe")).toBe("ready/object/steps");

    unmount();
    expect(target.state.disconnect).toHaveBeenCalledTimes(1);
  });
});

describe("useBackendSignal", () => {
  function Listener({ seen, parse = false }: { seen: string[]; parse?: boolean }) {
    useBackendSignal<{ code: string } | string>(
      "notify",
      (payload) => seen.push(typeof payload === "string" ? payload : payload.code),
      { parse },
    );
    return null;
  }

  async function ready(children: ReactNode) {
    const channel = channelOf();
    const target = fake();
    const view = render(<BackendProvider>{children}</BackendProvider>);
    await channel.ready(target.object);
    return { target, view };
  }

  it("does not subscribe before the connection is ready", () => {
    channelOf();
    const target = fake();
    render(
      <BackendProvider>
        <Listener seen={[]} />
      </BackendProvider>,
    );
    expect(target.notify.connect).not.toHaveBeenCalled();
  });

  it("delivers the payload raw, and parsed when asked", async () => {
    const raw: string[] = [];
    const parsed: string[] = [];
    const { target } = await ready(
      <>
        <Listener seen={raw} />
        <Listener seen={parsed} parse />
      </>,
    );

    act(() => {
      target.notify.emit(JSON.stringify({ code: "route.saved" }));
    });

    expect(raw).toEqual(['{"code":"route.saved"}']);
    expect(parsed).toEqual(["route.saved"]);
  });

  it("disconnects the signal on unmount", async () => {
    const seen: string[] = [];
    const { target, view } = await ready(<Listener seen={seen} />);
    // The listener's own handler is the last one connected; the provider's comes first.
    const handler = target.notify.connect.mock.calls.at(-1)?.[0];

    view.unmount();
    expect(target.notify.disconnect).toHaveBeenCalledWith(handler);
  });
});

describe("a notice emitted before anything listens", () => {
  function Listener({ seen }: { seen: string[] }) {
    useBackendSignal<string>("notify", (payload) => seen.push(payload));
    return null;
  }

  /** Python drains the start-up notices inside getState, before any listener has mounted. */
  function emittingDuringTheGetter(target: Fake, ...payloads: string[]) {
    target.getter.mockImplementation((cb: (json: string) => void) => {
      payloads.forEach((payload) => target.notify.emit(payload));
      void Promise.resolve().then(() => cb(JSON.stringify({ version: "1.0.0" })));
    });
  }

  it("reaches the first listener, oldest first, and only once", async () => {
    const channel = channelOf();
    const target = fake();
    emittingDuringTheGetter(target, "region.offscreen", "system.old_windows");
    const seen: string[] = [];

    render(
      <BackendProvider>
        <Listener seen={seen} />
      </BackendProvider>,
    );
    await channel.ready(target.object);
    expect(seen).toEqual(["region.offscreen", "system.old_windows"]);

    act(() => target.notify.emit("route.saved"));
    // Not twice: the provider stops holding the signal once a listener has taken it.
    expect(seen).toEqual(["region.offscreen", "system.old_windows", "route.saved"]);
  });

  it("keeps the signal connected throughout the hand-over", async () => {
    const channel = channelOf();
    const target = fake();
    const connectedAtEachDisconnect: number[] = [];
    const handlers = new Set<Handler>();
    target.notify.connect.mockImplementation((h) => void handlers.add(h));
    target.notify.disconnect.mockImplementation((h) => {
      handlers.delete(h);
      connectedAtEachDisconnect.push(handlers.size);
    });

    render(
      <BackendProvider>
        <Listener seen={[]} />
      </BackendProvider>,
    );
    await channel.ready(target.object);

    // QWebChannel stops forwarding a signal whose last handler goes: the listener must already
    // be connected when the provider lets go of its own.
    expect(connectedAtEachDisconnect).toEqual([1]);
  });

  it("is let go of on unmount even when nobody listened", async () => {
    const channel = channelOf();
    const target = fake();

    const { unmount } = render(
      <BackendProvider>
        <Probe />
      </BackendProvider>,
    );
    await channel.ready(target.object);
    const held = target.notify.connect.mock.calls[0]?.[0];
    expect(typeof held).toBe("function");

    unmount();
    expect(target.notify.disconnect).toHaveBeenCalledWith(held);
  });
});

describe("useBackendStore", () => {
  it("re-renders consumers when a component patches the store directly", async () => {
    const channel = channelOf();
    const target = fake({ version: "1.0.0" });
    const box: { store: Store<FakeState | null> | null } = { store: null };

    function Holder() {
      box.store = useBackendStore<FakeState>();
      return null;
    }

    render(
      <BackendProvider>
        <Holder />
        <Probe />
      </BackendProvider>,
    );
    await channel.ready(target.object);

    act(() => {
      box.store?.set({ version: "patched" });
    });
    expect(text("probe")).toBe("ready/object/patched");
  });
});

describe("a consumer outside a provider", () => {
  it("throws rather than handing back an empty connection", () => {
    // React re-throws the render error after logging it; the log is noise, not the assertion.
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/BackendProvider/);
    logged.mockRestore();
  });
});
