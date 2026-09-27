/** The Updates block: the two switches, Check now, the version line and a skipped version. */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeState } from "@/dev/mockState";
import type { UpdateState } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";

import UpdatesBlock, { type UpdatesBlockProps } from "./UpdatesBlock";

function en(key: string, params: Record<string, string> = {}): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return Object.entries(params).reduce((m, [k, v]) => m.replace(`{${k}}`, v), message);
}

function mount(update: UpdateState | undefined, props: Partial<UpdatesBlockProps> = {}) {
  const all: UpdatesBlockProps = {
    settings: makeState().settings,
    update,
    version: "1.0.0",
    isPortable: false,
    onChange: vi.fn(),
    onCheck: vi.fn(),
    onUnskip: vi.fn(),
    ...props,
  };
  render(
    <I18nProvider initial="en">
      <UpdatesBlock {...all} />
    </I18nProvider>,
  );
  return all;
}

function box(key: string): HTMLButtonElement {
  return screen.getByRole("switch", { name: en(key) });
}

function checkNow(): HTMLButtonElement {
  return screen.getByRole("button", { name: en("panel.updates.checkNow") });
}

describe("UpdatesBlock", () => {
  it("turns the automatic check and download on and off", () => {
    const p = mount({ phase: "idle" });

    fireEvent.click(box("panel.updates.autoCheck"));
    expect(p.onChange).toHaveBeenCalledWith("updates_auto_check", false);
    fireEvent.click(box("panel.updates.autoDownload"));
    expect(p.onChange).toHaveBeenCalledWith("updates_auto_download", false);
  });

  it("checks now on request", () => {
    const p = mount({ phase: "none" });
    expect(screen.getByText(en("panel.updates.latest"))).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: en("panel.updates.checkNow") }));
    expect(p.onCheck).toHaveBeenCalledTimes(1);
  });

  it.each(["checking", "downloading"] as const)(
    "does not start a second check while %s",
    (phase) => {
      mount({ phase, version: "1.2.0" });
      expect(checkNow().disabled).toBe(true);
    },
  );

  it("says why a copy that is not a Velopack install cannot update, and locks the controls", () => {
    mount({ phase: "disabled" });

    expect(screen.getByText(en("panel.updates.unavailable"))).toBeDefined();
    expect(checkNow().disabled).toBe(true);
    expect(box("panel.updates.autoCheck").disabled).toBe(true);
    expect(box("panel.updates.autoDownload").disabled).toBe(true);
  });

  it("shows the reason of a failed check", () => {
    mount({ phase: "failed", code: "update.failed", reason: "offline", stage: "check" });
    expect(screen.getByText(en("panel.updates.failed", { reason: "offline" }))).toBeDefined();
  });

  it("names the version and a portable copy", () => {
    mount({ phase: "idle" }, { version: "1.2.3", isPortable: true });
    expect(
      screen.getByText(en("panel.updates.current", { version: "1.2.3" }), { exact: false }),
    ).toBeDefined();
    expect(screen.getByText(en("panel.updates.portable"), { exact: false })).toBeDefined();
  });

  it("offers a skipped version again", () => {
    const settings = { ...makeState().settings, updates_skipped_version: "1.2.0" };
    const p = mount({ phase: "idle" }, { settings });

    expect(screen.getByText(en("panel.updates.skipped", { version: "1.2.0" }))).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: en("panel.updates.unskip") }));
    expect(p.onUnskip).toHaveBeenCalledTimes(1);
  });
});
