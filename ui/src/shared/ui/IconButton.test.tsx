/**
 * IconButton: that a glyph button is named in words, and named independently of its tooltip.
 *
 * `getByRole(role, { name })` is not sufficient here. The accessible-name algorithm falls back to
 * `title`, so a button carrying only a tooltip computes the same name as a properly labelled one
 * and a role-and-name query passes for both. The tests below therefore assert the `aria-label`
 * attribute directly wherever the distinction is the point.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import IconButton from "./IconButton";

describe("IconButton", () => {
  it("takes its accessible name from label, not from the glyph", () => {
    render(<IconButton label="Delete route" icon="×" />);

    const button = screen.getByRole("button", { name: "Delete route" });
    expect(button.getAttribute("aria-label")).toBe("Delete route");
  });

  it("hides the glyph from assistive technology, so it is not read as a word", () => {
    render(<IconButton label="Add map" icon="+" />);

    const glyph = screen.getByRole("button").querySelector("[aria-hidden='true']");
    expect(glyph?.textContent).toBe("+");
  });

  it("shows the name as the tooltip when no other tooltip is given", () => {
    render(<IconButton label="Open logs" icon="≡" />);

    expect(screen.getByRole("button").getAttribute("title")).toBe("Open logs");
  });

  it("keeps a tooltip that says something the name should not, such as a shortcut", () => {
    // A shortcut is not a name: "Ctrl+Z" tells a screen-reader user nothing about the action.
    render(<IconButton label="Undo" icon="↶" title="Ctrl+Z" />);

    const button = screen.getByRole("button", { name: "Undo" });
    expect(button.getAttribute("title")).toBe("Ctrl+Z");
    expect(button.getAttribute("aria-label")).toBe("Undo");
  });

  it("is type=button, so it cannot submit the form it sits in", () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <IconButton label="Pick colour" icon="●" />
      </form>,
    );

    screen.getByRole("button", { name: "Pick colour" }).click();

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("still submits when a caller asks for it explicitly", () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <IconButton label="Save" icon="✓" type="submit" />
      </form>,
    );

    screen.getByRole("button", { name: "Save" }).click();

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("passes the click through to the caller", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<IconButton label="Close" icon="×" onClick={onClick} />);

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("forwards the native attributes a caller needs, such as disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<IconButton label="Delete map" icon="×" disabled onClick={onClick} />);

    await user.click(screen.getByRole("button", { name: "Delete map" }));

    expect(onClick).not.toHaveBeenCalled();
  });
});
