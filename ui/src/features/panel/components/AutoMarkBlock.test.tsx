/**
 * Marking points on arrival is a card of its own: its switch is named by the heading, the radius
 * sits under it while it is on, and while it is off the card says how points get marked instead.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import AutoMarkBlock from "./AutoMarkBlock";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(auto: boolean, onToggle = vi.fn()) {
  render(
    <I18nProvider initial="en">
      <AutoMarkBlock
        auto={auto}
        radius={16 / 4096}
        map={[4096, 4096]}
        schema={{
          arrive_radius: { type: "float", default: 8 / 4096, min: 8 / 4096, max: 32 / 4096 },
        }}
        onToggle={onToggle}
        onRadius={vi.fn()}
      />
    </I18nProvider>,
  );
  return onToggle;
}

describe("AutoMarkBlock", () => {
  it("heads the card with a switch named by its heading", () => {
    mount(true);

    const toggle = screen.getByRole("switch", { name: en("panel.auto.title") });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("shows the radius in map pixels while on", () => {
    mount(true);

    expect(screen.getByRole("slider", { name: en("panel.auto.radius") })).toBeDefined();
    expect(screen.getByText("16 px of map")).toBeDefined();
  });

  it("says how points get marked instead while off", () => {
    mount(false);

    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.getByText(en("panel.auto.off"))).toBeDefined();
  });

  it("flips on a click", async () => {
    const user = userEvent.setup();
    const onToggle = mount(false);

    await user.click(screen.getByRole("switch", { name: en("panel.auto.title") }));

    expect(onToggle).toHaveBeenCalledWith(true);
  });
});
