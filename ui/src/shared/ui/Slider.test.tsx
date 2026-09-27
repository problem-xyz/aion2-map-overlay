/**
 * Slider is a thin wrapper over <input type="range">: it owns the readout and hands min/max/step
 * to the browser, which is what keeps a value inside its bounds. These pin the handover and the
 * shape of what comes back out -- a number, never the string the DOM actually carries.
 *
 * They also pin what it announces. The name is the label alone: the readout used to sit inside
 * the label and glue itself to it ("Opacity70%"), so the name changed on every drag step. The
 * formatted value lives in aria-valuetext now, which is where a reader expects it.
 *
 * jsdom does not implement arrow-key stepping on a range, and user-event does not simulate it
 * either, so value changes are driven with fireEvent.change; only focus is exercised for real.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Slider from "./Slider";

describe("Slider", () => {
  it("hands its bounds and step to the control that enforces them", () => {
    render(<Slider label="Opacity" value={70} min={10} max={90} step={5} onChange={vi.fn()} />);

    const slider = screen.getByRole("slider", { name: "Opacity" });
    expect(slider.getAttribute("min")).toBe("10");
    expect(slider.getAttribute("max")).toBe("90");
    expect(slider.getAttribute("step")).toBe("5");
    expect((slider as HTMLInputElement).value).toBe("70");
  });

  it("is named by its label alone, and says the formatted value as its value", () => {
    render(
      <Slider
        label="Opacity"
        value={70}
        min={0}
        max={100}
        step={5}
        format={(v) => `${v}%`}
        onChange={vi.fn()}
      />,
    );

    // getByRole computes the accessible name, so an exact string here is a measurement of what
    // a screen reader would announce -- not a check that some attribute exists.
    expect(screen.getByRole("slider", { name: "Opacity" })).toBeDefined();
    expect(screen.queryByRole("slider", { name: /70/ })).toBeNull();
    expect(screen.getByRole("slider").getAttribute("aria-valuetext")).toBe("70%");
  });

  it("leaves the value to be read off the number when there is nothing to format", () => {
    render(<Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={vi.fn()} />);

    expect(
      screen.getByRole("slider", { name: "Opacity" }).getAttribute("aria-valuetext"),
    ).toBeNull();
  });

  it("offers the hint as the control's description", () => {
    render(
      <Slider
        label="Opacity"
        value={70}
        min={0}
        max={100}
        step={5}
        hint="Lower is easier to see through"
        onChange={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("slider", {
        name: "Opacity",
        description: "Lower is easier to see through",
      }),
    ).toBeDefined();
  });

  it("reports the new value as a number", () => {
    const onChange = vi.fn();
    render(<Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={onChange} />);

    fireEvent.change(screen.getByRole("slider", { name: "Opacity" }), { target: { value: "35" } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(35);
  });

  it("stays controlled: the value on screen is the prop, not what was typed", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={onChange} />,
    );

    const slider = screen.getByRole("slider", { name: "Opacity" });
    fireEvent.change(slider, { target: { value: "35" } });
    expect((slider as HTMLInputElement).value).toBe("70");

    rerender(<Slider label="Opacity" value={35} min={0} max={100} step={5} onChange={onChange} />);
    expect((slider as HTMLInputElement).value).toBe("35");
  });

  it("shows the raw value, or the formatted one when a formatter is given", () => {
    const { rerender } = render(
      <Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={vi.fn()} />,
    );
    expect(screen.getByText("70")).toBeDefined();

    rerender(
      <Slider
        label="Opacity"
        value={70}
        min={0}
        max={100}
        step={5}
        format={(v) => `${v}%`}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("70%")).toBeDefined();
  });

  it("takes keyboard focus", async () => {
    const user = userEvent.setup();
    render(<Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={vi.fn()} />);

    await user.tab();

    expect(document.activeElement).toBe(screen.getByRole("slider", { name: "Opacity" }));
  });

  it("shows a hint only when one is given", () => {
    const { rerender } = render(
      <Slider label="Opacity" value={70} min={0} max={100} step={5} onChange={vi.fn()} />,
    );
    expect(screen.queryByText("Lower is easier to see through")).toBeNull();

    rerender(
      <Slider
        label="Opacity"
        value={70}
        min={0}
        max={100}
        step={5}
        hint="Lower is easier to see through"
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Lower is easier to see through")).toBeDefined();
  });
});
