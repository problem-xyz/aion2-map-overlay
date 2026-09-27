/**
 * The "i" beside a label: a button named after what it explains, whose explanation is its
 * description -- so a screen reader has the text without opening anything, in an engine with
 * no popover as well as in one with it.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import InfoTip from "./InfoTip";
import Slider from "./Slider";

const TEXT = "Keep it at or above the game's frame rate.";

describe("InfoTip", () => {
  it("is a button named after its topic and described by the explanation", () => {
    render(
      <I18nProvider initial="en">
        <InfoTip topic="Frame rate cap">{TEXT}</InfoTip>
      </I18nProvider>,
    );

    const button = screen.getByRole("button", { name: "About: Frame rate cap" });
    // closed, the tip is out of the page's flow, and only its text is read through the button
    const tip = screen.getByRole("tooltip", { hidden: true });
    expect(button.getAttribute("aria-describedby")).toBe(tip.id);
    expect(tip.textContent).toBe(TEXT);
  });

  it("sits beside a field's label without becoming part of the field's name", () => {
    render(
      <I18nProvider initial="en">
        <Slider
          label="Frame rate cap"
          value={60}
          min={30}
          max={240}
          step={5}
          tip={TEXT}
          onChange={() => {}}
        />
      </I18nProvider>,
    );

    expect(screen.getByRole("slider", { name: "Frame rate cap" })).toBeDefined();
    expect(screen.getByRole("button", { name: "About: Frame rate cap" })).toBeDefined();
  });
});
