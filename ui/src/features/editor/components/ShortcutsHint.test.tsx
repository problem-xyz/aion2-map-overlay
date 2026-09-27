/**
 * The keys: a strip always on show, and the full card over it on its button or `?`.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import ShortcutsHint from "./ShortcutsHint";

function mount() {
  return render(
    <I18nProvider initial="en">
      <ShortcutsHint />
      <input aria-label="label" />
    </I18nProvider>,
  );
}

const more = () => screen.getByRole("button", { name: /All keys/ });

describe("ShortcutsHint", () => {
  it("shows the strip, with the full card folded away", () => {
    mount();

    expect(screen.getByText("add a point")).toBeDefined();
    expect(more().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Delete the selected point")).toBeNull();
  });

  it("opens the full card from its button, and closes it on Escape", async () => {
    const user = userEvent.setup();
    mount();

    await user.click(more());
    expect(screen.getByRole("heading", { name: "Shortcuts" })).toBeDefined();
    expect(screen.getByText("Move the selected point along the route")).toBeDefined();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("heading", { name: "Shortcuts" })).toBeNull();
  });

  it("toggles on ?, but not while a field is being typed in", async () => {
    const user = userEvent.setup();
    mount();

    await user.keyboard("?");
    expect(more().getAttribute("aria-expanded")).toBe("true");

    await user.click(screen.getByRole("textbox", { name: "label" }));
    await user.keyboard("?");
    expect(more().getAttribute("aria-expanded")).toBe("true");
  });
});
