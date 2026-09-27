/**
 * The block's on/off control. It used to be a bare checkbox inside a label with no text, which
 * reads as an unnamed checkbox; it is now a switch that borrows the block heading for its name.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import PreviewBlock from "./PreviewBlock";

vi.mock("@/shared/backend/BackendProvider", () => ({ useBackendSignal: () => undefined }));

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(enabled: boolean, onToggle = vi.fn()) {
  render(
    <I18nProvider initial="en">
      <PreviewBlock enabled={enabled} running={false} showAnchor={false} onToggle={onToggle} />
    </I18nProvider>,
  );
  return onToggle;
}

describe("PreviewBlock", () => {
  it("offers a switch named by the block heading", () => {
    mount(false);

    expect(screen.getByRole("switch", { name: en("panel.preview.title") })).toBeDefined();
  });

  it("reports its state as aria-checked", () => {
    mount(false);
    expect(screen.getByRole("switch", { checked: false })).toBeDefined();
    expect(screen.queryByRole("switch", { checked: true })).toBeNull();
  });

  it("reports the state the other way round when it is on", () => {
    mount(true);
    expect(screen.getByRole("switch", { checked: true })).toBeDefined();
  });

  it("flips on a click", async () => {
    const user = userEvent.setup();
    const onToggle = mount(false);

    await user.click(screen.getByRole("switch"));

    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("flips from the keyboard", async () => {
    const user = userEvent.setup();
    const onToggle = mount(true);

    screen.getByRole("switch").focus();
    await user.keyboard(" ");

    expect(onToggle).toHaveBeenCalledWith(false);
  });
});
