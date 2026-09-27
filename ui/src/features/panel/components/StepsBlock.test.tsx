/**
 * The checklist's settings card: the pin, a switch named by its label, and the zoom, a scale on
 * a slider. Switching the checklist on and off is the run row's, not this card's.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import StepsBlock from "./StepsBlock";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(pinned: boolean) {
  render(
    <I18nProvider initial="en">
      <StepsBlock
        pinned={pinned}
        scale={1}
        schema={{ steps_scale: { type: "float", default: 1, min: 0.5, max: 1.5 } }}
        onPin={vi.fn()}
        onScale={vi.fn()}
      />
    </I18nProvider>,
  );
}

describe("StepsBlock", () => {
  it("has no switch of its own for showing the checklist: only the pin", () => {
    mount(false);

    expect(screen.getAllByRole("switch")).toHaveLength(1);
    expect(screen.getByRole("switch", { name: en("panel.steps.pin") })).toBeDefined();
  });

  it("names the pin by its label and describes it by its hint", () => {
    mount(true);

    const pin = screen.getByRole("switch", { name: en("panel.steps.pin") });
    expect(pin.getAttribute("aria-checked")).toBe("true");
    const hint = document.getElementById(pin.getAttribute("aria-describedby") ?? "");
    expect(hint?.textContent).toBe(en("panel.steps.pinHint"));
  });

  it("offers the zoom as a scale on a slider, read out as a percentage", () => {
    mount(false);

    const slider = screen.getByRole("slider", { name: en("panel.steps.sizeLabel") });
    expect(slider.getAttribute("aria-valuetext")).toBe("100%");
    expect([slider.getAttribute("min"), slider.getAttribute("max")]).toEqual(["0.5", "1.5"]);
  });
});
