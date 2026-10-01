/**
 * The run row on a Windows that can hide the overlay from capture, and on one that cannot.
 *
 * On the second the "Visible in screen recordings" box has to say what is true -- the overlay
 * is visible -- and must not be switchable, the warning has to be the box's description, and
 * the tooltip that tells the user to turn it on while recording has to go. The checklist is
 * switched here too, beside the arrows, and the slots drop their names where Start would be cut
 * short.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import RunRow, { type RunRowProps } from "./RunRow";

// jsdom has no ResizeObserver, and lays nothing out: every width it reports is 0.
class NoopResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = NoopResizeObserver;

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(props: Partial<RunRowProps> = {}) {
  const all: RunRowProps = {
    running: false,
    canStart: true,
    checklistVisible: false,
    overlayVisible: true,
    cubesVisible: false,
    tracesVisible: true,
    captureVisible: false,
    captureExclusion: true,
    onStart: vi.fn(),
    onStop: vi.fn(),
    onChecklistVisible: vi.fn(),
    onOverlayVisible: vi.fn(),
    onCubesVisible: vi.fn(),
    onTracesVisible: vi.fn(),
    onCaptureVisible: vi.fn(),
    ...props,
  };
  render(
    <I18nProvider initial="en">
      <RunRow {...all} />
    </I18nProvider>,
  );
  return all;
}

function recordingBox(): HTMLInputElement {
  return screen.getByRole("checkbox", { name: en("panel.run.visibleInRecording") });
}

describe("RunRow", () => {
  it("switches the cubes on their own, beside the arrows", () => {
    const props = mount({ cubesVisible: false });
    const box = screen.getByRole<HTMLInputElement>("checkbox", { name: en("panel.run.cubes") });

    expect(box.checked).toBe(false);
    fireEvent.click(box);
    expect(props.onCubesVisible).toHaveBeenCalledWith(true);
    expect(props.onOverlayVisible).not.toHaveBeenCalled();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("switches the checklist from its own slot", () => {
    const props = mount({ checklistVisible: false });
    const box = screen.getByRole("checkbox", { name: en("panel.run.checklist") });

    expect(box.closest("label")?.getAttribute("title")).toBe(en("panel.run.checklist"));
    fireEvent.click(box);
    expect(props.onChecklistVisible).toHaveBeenCalledWith(true);
  });

  it("keeps the slots' names while Start has room for its own", () => {
    mount();
    expect(document.querySelector(".pn-run")?.classList.contains("compact")).toBe(false);
  });

  it("shows the slots' icons alone where Start would be cut short", () => {
    vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(210);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(170);
    mount();

    expect(document.querySelector(".pn-run")?.classList.contains("compact")).toBe(true);
    // the names stay what the boxes are called
    expect(screen.getByRole("checkbox", { name: en("panel.run.showArrows") })).toBeDefined();
  });

  it.each([true, undefined])(
    "follows the setting and warns of nothing where capture can be excluded (%s)",
    (captureExclusion) => {
      const props = mount({ captureExclusion, captureVisible: false });
      const box = recordingBox();

      expect(box.checked).toBe(false);
      expect(box.disabled).toBe(false);
      expect(box.getAttribute("aria-describedby")).toBeNull();
      expect(screen.queryByText(en("panel.run.captureExclusionOff"))).toBeNull();
      expect(box.closest("label")?.getAttribute("title")).toBe(
        en("panel.run.visibleInRecordingTip"),
      );

      fireEvent.click(box);
      expect(props.onCaptureVisible).toHaveBeenCalledWith(true);
    },
  );

  it("shows the box ticked and locked, described by the warning, on an older Windows", () => {
    mount({ captureExclusion: false, captureVisible: false });
    const box = recordingBox();

    expect(box.checked).toBe(true);
    expect(box.disabled).toBe(true);

    const warning = screen.getByText(en("panel.run.captureExclusionOff"));
    expect(warning.id).not.toBe("");
    expect(box.getAttribute("aria-describedby")).toBe(warning.id);
    // "Turn this on while you record" would contradict a box that is on and cannot be changed.
    expect(box.closest("label")?.hasAttribute("title")).toBe(false);
  });

  it("offers Stop, and no Start, while running", () => {
    const running = mount({ running: true });
    expect(screen.queryByRole("button", { name: en("panel.run.start") })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: en("panel.run.stop") }));
    expect(running.onStop).toHaveBeenCalledTimes(1);
  });

  it("lets Start run with no map area yet", () => {
    mount({ canStart: true });
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: en("panel.run.start") }).disabled,
    ).toBe(false);
  });

  it("lays the gold sheen on Start only while it can start", () => {
    mount({ canStart: true });
    expect(document.querySelector(".btn-start .ui-sheen-gold")).not.toBeNull();
  });

  it("keeps a Start that cannot run still", () => {
    mount({ canStart: false });
    expect(document.querySelector(".btn-start .ui-sheen")).toBeNull();
  });
});
