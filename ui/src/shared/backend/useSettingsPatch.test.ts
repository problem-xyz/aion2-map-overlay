/**
 * What a settings patch carries. The debounce itself is useDebouncedCallback's and is pinned in
 * its own test; this file pins that a patch holds what changed since the last send and nothing
 * older -- a patch that re-sent every key ever touched would undo a reset to defaults the next
 * time any control moved.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AppState, Settings } from "@/shared/backend/contract";
import { type Store, createStore } from "@/shared/backend/store";

import { SETTINGS_DEBOUNCE_MS, useSettingsPatch } from "./useSettingsPatch";

const backend = vi.hoisted(() => ({
  updateSettings: vi.fn<(patch: Partial<Settings>) => void>(),
  store: null as Store<AppState | null> | null,
}));

vi.mock("@/shared/backend/hooks", () => ({
  useApi: () => ({ updateSettings: backend.updateSettings }),
}));

vi.mock("@/shared/backend/BackendProvider", () => ({
  useBackendStore: () => backend.store,
}));

function settle() {
  act(() => {
    vi.advanceTimersByTime(SETTINGS_DEBOUNCE_MS);
  });
}

describe("useSettingsPatch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    backend.updateSettings.mockClear();
    backend.store = createStore<AppState | null>({ settings: { fps: 60 } } as AppState);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("applies a change to the local state at once and sends it after the debounce", () => {
    const { result } = renderHook(() => useSettingsPatch());

    act(() => result.current("fps", 90));

    expect(backend.store?.get()?.settings.fps).toBe(90);
    expect(backend.updateSettings).not.toHaveBeenCalled();
    settle();
    expect(backend.updateSettings.mock.calls).toEqual([[{ fps: 90 }]]);
  });

  it("sends only what changed since the last patch", () => {
    const { result } = renderHook(() => useSettingsPatch());

    act(() => result.current("opacity", 0.4));
    settle();
    act(() => result.current("fps", 90));
    settle();

    expect(backend.updateSettings.mock.calls).toEqual([[{ opacity: 0.4 }], [{ fps: 90 }]]);
  });

  it("drops an unsent change on cancel, so it cannot land after a reset", () => {
    const { result } = renderHook(() => useSettingsPatch());

    act(() => result.current("opacity", 0.4));
    act(() => result.current.cancel());
    settle();
    act(() => result.current("fps", 90));
    settle();

    expect(backend.updateSettings.mock.calls).toEqual([[{ fps: 90 }]]);
  });
});
