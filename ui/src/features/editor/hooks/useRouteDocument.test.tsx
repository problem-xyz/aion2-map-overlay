/**
 * Removing points: which point the inspector moves on to after a deletion, and "delete all"
 * asking first and going back in one undo.
 *
 * The backend is not needed for either, so `useApi` hands back nothing; `useConfirm` is the
 * dialog's answer, set per test.
 */

import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import { useRouteDocument } from "./useRouteDocument";

vi.mock("@/shared/backend/hooks", () => ({ useApi: () => null }));

const answer = vi.fn<(message: string, options?: object) => Promise<boolean>>();
vi.mock("@/shared/hooks/useConfirm", () => ({ useConfirm: () => answer }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <I18nProvider initial="en">{children}</I18nProvider>
);

/** A document with three points, from left to right, none selected. */
function mount() {
  const hook = renderHook(() => useRouteDocument([]), { wrapper });
  act(() => {
    for (const x of [10, 20, 30]) hook.result.current.actions.addMarker({ x, y: 0 });
  });
  act(() => hook.result.current.actions.select(null));
  return hook;
}

const ids = (hook: ReturnType<typeof mount>) => hook.result.current.markers.map((m) => m.id);

describe("useRouteDocument: removing points", () => {
  beforeEach(() => {
    answer.mockReset();
    answer.mockResolvedValue(true);
  });

  it("selects the point that takes the deleted one's place", () => {
    const hook = mount();
    const [first, second, third] = ids(hook);
    act(() => hook.result.current.actions.select(second ?? null));
    act(() => hook.result.current.actions.deleteMarker(second ?? -1));
    expect(ids(hook)).toEqual([first, third]);
    expect(hook.result.current.selectedId).toBe(third);
  });

  it("falls back to the point before when the last one goes, and to nothing when none is left", () => {
    const hook = mount();
    const [first, second, third] = ids(hook);
    act(() => hook.result.current.actions.select(third ?? null));
    act(() => hook.result.current.actions.deleteMarker(third ?? -1));
    expect(hook.result.current.selectedId).toBe(second);
    act(() => hook.result.current.actions.deleteMarker(second ?? -1));
    act(() => hook.result.current.actions.deleteMarker(first ?? -1));
    expect(hook.result.current.markers).toEqual([]);
    expect(hook.result.current.selectedId).toBeNull();
  });

  it("leaves another selection where it is", () => {
    const hook = mount();
    const [first, , third] = ids(hook);
    act(() => hook.result.current.actions.select(first ?? null));
    act(() => hook.result.current.actions.deleteMarker(third ?? -1));
    expect(hook.result.current.selectedId).toBe(first);
  });

  it("deletes every point after a yes, and one undo brings them all back", async () => {
    const hook = mount();
    const before = hook.result.current.markers;
    act(() => hook.result.current.actions.select(before[1]?.id ?? null));
    await act(async () => {
      hook.result.current.actions.clearMarkers();
      await Promise.resolve();
    });
    expect(answer).toHaveBeenCalledWith(expect.any(String), {
      confirmLabel: "Delete all",
      danger: true,
    });
    expect(hook.result.current.markers).toEqual([]);
    expect(hook.result.current.selectedId).toBeNull();
    act(() => hook.result.current.actions.undo());
    expect(hook.result.current.markers).toBe(before);
  });

  it("keeps the points on a no", async () => {
    answer.mockResolvedValue(false);
    const hook = mount();
    const before = hook.result.current.markers;
    await act(async () => {
      hook.result.current.actions.clearMarkers();
      await Promise.resolve();
    });
    expect(hook.result.current.markers).toBe(before);
  });
});
