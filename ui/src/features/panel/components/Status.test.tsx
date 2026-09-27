/**
 * Where the live region sits, and where it must not.
 *
 * The engine pushes stats about four times a second. A live region around the header as a whole
 * would hand a screen reader a fresh fps figure on every tick and talk over whatever the user
 * was listening to, so the region is the status sentence alone -- a handful of changes per
 * session. These tests fail if it is ever widened.
 */

import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Stats } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";

import Status from "./Status";

// Status subscribes to statsChanged itself, so the test needs the handler rather than a backend.
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

const STATS: Stats = {
  found: true,
  anchored: true,
  fps: 60,
  processMs: 8,
  detectMs: 12,
  flowPoints: 40,
  matches: 120,
  inliers: 80,
  reprojError: 2,
  backend: "dxgi",
};

function mount(running: boolean) {
  return render(
    <I18nProvider initial="en">
      <Status running={running} />
    </I18nProvider>,
  );
}

function liveRegions(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[aria-live]")];
}

describe("Status", () => {
  beforeEach(() => {
    signal.emit = null;
  });

  it("puts the polite live region on the status sentence and nowhere else", () => {
    mount(false);

    const regions = liveRegions();
    expect(regions).toHaveLength(1);
    expect(regions[0]?.getAttribute("aria-live")).toBe("polite");
    expect(regions[0]?.textContent).toBe(en("panel.status.idle"));
  });

  it("leaves the counters outside the live region", () => {
    mount(true);
    act(() => signal.emit?.(STATS));

    // the labels are always drawn, the numbers arrive with the payload: neither may be announced
    for (const key of ["panel.stats.fps", "panel.stats.frame", "panel.stats.detect"]) {
      expect(screen.getByText(en(key)).closest("[aria-live]")).toBeNull();
    }
    expect(screen.getByText("60").closest("[aria-live]")).toBeNull();
    expect(liveRegions()).toHaveLength(1);
  });

  it("changes the sentence inside the same region rather than replacing it", () => {
    const view = mount(false);
    const before = liveRegions()[0];

    view.rerender(
      <I18nProvider initial="en">
        <Status running />
      </I18nProvider>,
    );

    const after = liveRegions()[0];
    expect(after).toBe(before); // a region added at the same moment as its text is not announced
    expect(after?.textContent).toBe(en("panel.status.searching"));
  });

  it("does not announce a stats tick", () => {
    mount(true);
    const region = liveRegions()[0];
    const before = region?.textContent;

    act(() => signal.emit?.({ ...STATS, fps: 61 }));

    expect(region?.textContent).toBe(en("panel.status.found"));
    expect(before).toBe(en("panel.status.searching"));
    // the figure changed, and it changed outside the region
    expect(screen.getByText("61").closest("[aria-live]")).toBeNull();
  });

  it("keeps the borderless hint out of the header, so Start/Stop below it never moves", () => {
    mount(true);
    expect(screen.queryByText(en("panel.status.fullscreenHint"))).toBeNull();
  });
});
