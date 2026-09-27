/**
 * The warm-up: the sections not on screen are drawn once, shortly after the panel opens, and
 * taken away again -- and while they are there nothing can reach them or read them out.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WarmUp, { WARM_DELAY_MS, WARM_HOLD_MS } from "./WarmUp";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function mount() {
  render(
    <WarmUp>
      <button type="button">Hidden settings</button>
    </WarmUp>,
  );
}

describe("WarmUp", () => {
  it("waits for the panel's own first frames before it draws anything", () => {
    mount();
    expect(document.querySelector(".pn-warm")).toBeNull();
  });

  it("draws the sections for a moment, out of reach and out of the accessibility tree", () => {
    mount();
    act(() => {
      vi.advanceTimersByTime(WARM_DELAY_MS);
    });

    const warm = document.querySelector(".pn-warm");
    expect(warm?.getAttribute("aria-hidden")).toBe("true");
    expect(warm?.hasAttribute("inert")).toBe(true);
    expect(screen.queryByRole("button", { name: "Hidden settings" })).toBeNull();
  });

  it("takes them away again", () => {
    mount();
    act(() => {
      vi.advanceTimersByTime(WARM_DELAY_MS);
    });
    act(() => {
      vi.advanceTimersByTime(WARM_HOLD_MS);
    });

    expect(document.querySelector(".pn-warm")).toBeNull();
  });
});
