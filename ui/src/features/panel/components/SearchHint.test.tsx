/**
 * When the borderless-windowed hint comes up: only after the search has gone on for a while,
 * counted from the first frame of the run, not from Start.
 *
 * It pushes everything below the run row down, so it must not flash on every Start, or every
 * time the in-game map is closed for a moment and found again.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Stats } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";

import SearchHint, { SEARCH_HINT_DELAY_MS } from "./SearchHint";

const signal = vi.hoisted(() => ({
  emit: null as ((stats: Stats | null) => void) | null,
}));

vi.mock("@/shared/backend/BackendProvider", () => ({
  useBackendSignal: (_name: string, handler: (stats: Stats | null) => void) => {
    signal.emit = handler;
  },
}));

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

const FOUND = { found: true, anchored: true } as Stats;
const LOST = { found: false, anchored: false } as Stats;

function mount(running: boolean) {
  const view = render(
    <I18nProvider initial="en">
      <SearchHint running={running} />
    </I18nProvider>,
  );
  return (next: boolean) =>
    view.rerender(
      <I18nProvider initial="en">
        <SearchHint running={next} />
      </I18nProvider>,
    );
}

function shown(): boolean {
  return screen.queryByText(en("panel.status.fullscreenHint")) !== null;
}

function wait(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

describe("SearchHint", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    signal.emit = null;
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("says nothing while stopped, however long", () => {
    mount(false);
    wait(SEARCH_HINT_DELAY_MS * 2);
    expect(shown()).toBe(false);
  });

  it("waits for the first frame: preparing a large map is not searching", () => {
    mount(true);
    wait(SEARCH_HINT_DELAY_MS * 2);
    expect(shown()).toBe(false);

    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS - 1);
    expect(shown()).toBe(false);
    wait(1);
    expect(shown()).toBe(true);
  });

  it("comes up once a search has lasted the delay, and goes when the map is found", () => {
    mount(true);
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS - 1);
    expect(shown()).toBe(false);

    wait(1);
    expect(shown()).toBe(true);

    act(() => signal.emit?.(FOUND));
    expect(shown()).toBe(false);
  });

  it("does not flash for a map found before the delay, or lost again for a moment", () => {
    mount(true);
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS / 2);
    act(() => signal.emit?.(FOUND));
    wait(SEARCH_HINT_DELAY_MS);
    expect(shown()).toBe(false);

    // the in-game map closed and reopened: the wait starts over, it does not carry on
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS / 2);
    act(() => signal.emit?.(FOUND));
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS / 2);
    expect(shown()).toBe(false);
    wait(SEARCH_HINT_DELAY_MS / 2);
    expect(shown()).toBe(true);
  });

  it("goes with Stop and waits again after the next Start", () => {
    const rerender = mount(true);
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS);
    expect(shown()).toBe(true);

    rerender(false);
    expect(shown()).toBe(false);
    // the last tick of the run just stopped, delivered after Stop
    act(() => signal.emit?.(LOST));

    rerender(true);
    wait(SEARCH_HINT_DELAY_MS);
    expect(shown()).toBe(false);
    act(() => signal.emit?.(LOST));
    wait(SEARCH_HINT_DELAY_MS);
    expect(shown()).toBe(true);
  });
});
