import { describe, expect, it } from "vitest";

import type { AppState } from "@/shared/backend/contract";

import { sameForPanel } from "./PanelPage";

const base = {
  running: false,
  settings: {},
  update: { phase: "idle" },
  timers: null,
} as unknown as AppState;

describe("sameForPanel", () => {
  it("lets an update or timers tick through without a re-render", () => {
    expect(
      sameForPanel(base, { ...base, update: { phase: "downloading" } } as unknown as AppState),
    ).toBe(true);
    expect(sameForPanel(base, { ...base, timers: {} } as unknown as AppState)).toBe(true);
  });

  it("re-renders for anything the map tool shows", () => {
    expect(sameForPanel(base, { ...base, running: true })).toBe(false);
    expect(sameForPanel(base, { ...base, settings: { ...base.settings } })).toBe(false);
    expect(sameForPanel(base, { ...base, extra: 1 } as unknown as AppState)).toBe(false);
  });
});
