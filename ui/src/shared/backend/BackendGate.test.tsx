/**
 * What the window shows before it has a backend, and that it shows something at all.
 *
 * The gate's whole job is that neither "connecting" nor "error" is ever a blank window, and that
 * the children stay behind it until the connection is usable. The expected sentences are looked
 * up in the shipped catalogue rather than typed out here: what is pinned is which key the gate
 * reaches for, not this week's wording.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import { BackendGate } from "./BackendGate";
import { BackendProvider } from "./BackendProvider";
import { BackendError, connectObject } from "./transport";

// Only the connection is replaced: BackendError has to stay the real class, since the gate picks
// its message by `instanceof` and then by `error.code`.
vi.mock("./transport", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./transport")>()),
  connectObject: vi.fn(),
}));

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
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

/** Enough of a Qt object for the provider to reach "ready": one signal and one getter. */
function fakeObject(): Record<string, unknown> {
  return {
    stateChanged: { connect: vi.fn(), disconnect: vi.fn() },
    getState: (cb: (json: string) => void) => cb("{}"),
  };
}

function renderGate(quiet = false) {
  const channel = channelOf();
  const view = render(
    <I18nProvider initial="en">
      <BackendProvider>
        <BackendGate quiet={quiet}>
          <div data-testid="child">child</div>
        </BackendGate>
      </BackendProvider>
    </I18nProvider>,
  );
  return { channel, view };
}

beforeEach(() => {
  vi.mocked(connectObject).mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BackendGate while connecting", () => {
  it("says it is connecting and keeps the children back", () => {
    renderGate();

    expect(screen.getByText(en("common.connecting"))).toBeTruthy();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("renders nothing at all when quiet, so the plaque does not cover the game", () => {
    const { view } = renderGate(true);

    expect(view.container.innerHTML).toBe("");
  });
});

describe("BackendGate once ready", () => {
  it("hands the window over to the children", async () => {
    const { channel } = renderGate();

    await channel.ready(fakeObject());

    expect(screen.getByTestId("child")).toBeTruthy();
    expect(screen.queryByText(en("common.connecting"))).toBeNull();
  });

  it("hands the window over to the children when quiet too", async () => {
    const { channel } = renderGate(true);

    await channel.ready(fakeObject());

    expect(screen.getByTestId("child")).toBeTruthy();
  });
});

describe("BackendGate on a failed connection", () => {
  it("explains the failure with the sentence its code names", async () => {
    const { channel } = renderGate();

    await channel.fail(new BackendError("backend.noTransport"));

    expect(screen.getByText(en("common.noEngine"))).toBeTruthy();
    expect(screen.getByText(en("common.backend.noTransport"))).toBeTruthy();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("falls back to the error's own message for a code this build has no sentence for", async () => {
    // The catalogue reports the miss, which is correct and not what this test is about.
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const { channel } = renderGate();

    await channel.fail(new BackendError("backend.fromALaterPython", "the channel gave up"));

    expect(screen.getByText("the channel gave up")).toBeTruthy();
    // The bare key is not a sentence, so it must never reach the window.
    expect(screen.queryByText("common.backend.fromALaterPython")).toBeNull();
  });

  it("shows a plain Error's message, since it carries no code to look up", async () => {
    const { channel } = renderGate();

    await channel.fail(new Error("channel exploded"));

    expect(screen.getByText("channel exploded")).toBeTruthy();
  });

  it("renders nothing at all when quiet", async () => {
    const { channel, view } = renderGate(true);

    await channel.fail(new BackendError("backend.noTransport"));

    expect(view.container.innerHTML).toBe("");
  });
});
