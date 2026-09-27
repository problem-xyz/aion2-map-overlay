/**
 * Segmented is a radio group, so what is worth pinning is what it announces and what the
 * keyboard does with it: one tab stop for the whole row, arrows moving the choice along it, and
 * the caller's exact option value coming back out. The `on` class is styling and deliberately
 * not asserted -- `aria-checked` is the contract, the highlight only follows it.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type FormEvent } from "react";
import { describe, expect, it, vi } from "vitest";

import Segmented from "./Segmented";

const OPTIONS = [
  { value: "fast", label: "Fast" },
  { value: "balanced", label: "Balanced" },
  { value: "best", label: "Best" },
];

/** The arrows only tell their whole story when the value comes back changed. */
function Controlled({ start }: { start: string }) {
  const [value, setValue] = useState(start);
  return <Segmented label="Quality" value={value} options={OPTIONS} onChange={setValue} />;
}

describe("Segmented", () => {
  it("shows one radio per option, named by its label", () => {
    render(<Segmented label="Quality" value="fast" options={OPTIONS} onChange={vi.fn()} />);

    expect(screen.getAllByRole("radio").map((b) => b.textContent)).toEqual([
      "Fast",
      "Balanced",
      "Best",
    ]);
  });

  it("gives the group the field's own label as its name", () => {
    render(<Segmented label="Quality" value="fast" options={OPTIONS} onChange={vi.fn()} />);

    // The name is computed from aria-labelledby, not read off an attribute: this is what a
    // screen reader would announce before the options.
    expect(screen.getByRole("radiogroup", { name: "Quality" })).toBeDefined();
  });

  it("marks the current option, and only that one, as checked", () => {
    const { rerender } = render(
      <Segmented label="Quality" value="fast" options={OPTIONS} onChange={vi.fn()} />,
    );
    expect(screen.getByRole("radio", { checked: true }).textContent).toBe("Fast");
    expect(screen.getAllByRole("radio", { checked: false }).map((b) => b.textContent)).toEqual([
      "Balanced",
      "Best",
    ]);

    rerender(<Segmented label="Quality" value="best" options={OPTIONS} onChange={vi.fn()} />);
    expect(screen.getByRole("radio", { checked: true }).textContent).toBe("Best");
  });

  it("reports the option's own value when it is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Segmented label="Quality" value="fast" options={OPTIONS} onChange={onChange} />);

    await user.click(screen.getByRole("radio", { name: "Best" }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("best");
  });

  it("keeps numeric option values numeric", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Segmented
        label="Scale"
        value={1}
        options={[
          { value: 1, label: "1x" },
          { value: 2, label: "2x" },
        ]}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("radio", { name: "2x" }));

    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("is one tab stop: Tab lands on the current option and the next Tab leaves the group", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Segmented label="Quality" value="balanced" options={OPTIONS} onChange={vi.fn()} />
        <button type="button">After</button>
      </>,
    );

    await user.tab();
    expect(document.activeElement?.textContent).toBe("Balanced");

    await user.tab();
    expect(document.activeElement?.textContent).toBe("After");
  });

  it("moves the choice with the arrow keys, wrapping at both ends", async () => {
    const user = userEvent.setup();
    render(<Controlled start="fast" />);
    const checked = () => screen.getByRole("radio", { checked: true }).textContent;

    await user.tab();
    expect(document.activeElement?.textContent).toBe("Fast");

    await user.keyboard("{ArrowRight}");
    expect(checked()).toBe("Balanced");
    // Selection follows focus, the way the platform's own radio buttons behave.
    expect(document.activeElement?.textContent).toBe("Balanced");

    await user.keyboard("{ArrowDown}");
    expect(checked()).toBe("Best");

    await user.keyboard("{ArrowRight}");
    expect(checked()).toBe("Fast");

    await user.keyboard("{ArrowLeft}");
    expect(checked()).toBe("Best");

    await user.keyboard("{ArrowUp}");
    expect(checked()).toBe("Balanced");
    expect(document.activeElement?.textContent).toBe("Balanced");
  });

  it("fires the focused option on Enter and on Space", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Segmented label="Quality" value="fast" options={OPTIONS} onChange={onChange} />);

    screen.getByRole("radio", { name: "Balanced" }).focus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");

    expect(onChange.mock.calls).toEqual([["balanced"], ["balanced"]]);
  });

  it("does not submit the form it sits in", async () => {
    const onSubmit = vi.fn((e: FormEvent) => e.preventDefault());
    const user = userEvent.setup();
    render(
      <form onSubmit={onSubmit}>
        <Segmented label="Quality" value="fast" options={OPTIONS} onChange={vi.fn()} />
      </form>,
    );

    await user.click(screen.getByRole("radio", { name: "Best" }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows a hint only when one is given", () => {
    const { rerender } = render(
      <Segmented label="Quality" value="fast" options={OPTIONS} onChange={vi.fn()} />,
    );
    expect(screen.queryByText("Slower, but steadier")).toBeNull();

    rerender(
      <Segmented
        label="Quality"
        value="fast"
        options={OPTIONS}
        onChange={vi.fn()}
        hint="Slower, but steadier"
      />,
    );
    expect(screen.getByText("Slower, but steadier")).toBeDefined();
  });
});
