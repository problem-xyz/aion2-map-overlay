import { afterEach, describe, expect, it, vi } from "vitest";

import { FOCUS_ATTRIBUTE, followWindowFocus } from "./windowFocus";

afterEach(() => {
  vi.restoreAllMocks();
});

function focus(has: boolean, event: "focus" | "blur") {
  vi.spyOn(document, "hasFocus").mockReturnValue(has);
  window.dispatchEvent(new Event(event));
}

describe("followWindowFocus", () => {
  it("marks the root as the window gains and loses the focus", () => {
    const root = document.createElement("div");
    vi.spyOn(document, "hasFocus").mockReturnValue(true);
    const stop = followWindowFocus(root);
    expect(root.hasAttribute(FOCUS_ATTRIBUTE)).toBe(true);

    focus(false, "blur");
    expect(root.hasAttribute(FOCUS_ATTRIBUTE)).toBe(false);

    focus(true, "focus");
    expect(root.hasAttribute(FOCUS_ATTRIBUTE)).toBe(true);
    stop();
  });

  it("starts unmarked in a window that opens in the background", () => {
    const root = document.createElement("div");
    vi.spyOn(document, "hasFocus").mockReturnValue(false);
    const stop = followWindowFocus(root);

    expect(root.hasAttribute(FOCUS_ATTRIBUTE)).toBe(false);
    stop();
  });

  it("stops following once stopped", () => {
    const root = document.createElement("div");
    vi.spyOn(document, "hasFocus").mockReturnValue(true);
    followWindowFocus(root)();

    focus(false, "blur");
    expect(root.hasAttribute(FOCUS_ATTRIBUTE)).toBe(true);
  });
});
