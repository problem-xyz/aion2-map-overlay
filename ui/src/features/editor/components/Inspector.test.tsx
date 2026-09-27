/**
 * The inspector of the selected point: its heading, its label, its colour and its moves.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { EditorMarker } from "../lib/routeDoc";
import { EditorWrap, stubActions, stubState } from "../testing";

import Inspector from "./Inspector";

const MARKERS: EditorMarker[] = [
  { id: 1, x: 0, y: 0, text: "gate" },
  { id: 2, x: 30, y: 40, text: "camp", color: "#6ea8ff" },
  { id: 3, x: 60, y: 80, text: "" },
];

function mount(selectedId: number | null) {
  const actions = stubActions();
  render(
    <EditorWrap state={stubState({ markers: MARKERS, selectedId })} actions={actions}>
      <Inspector />
    </EditorWrap>,
  );
  return actions;
}

describe("Inspector", () => {
  it("shows nothing while no point is selected", () => {
    mount(null);

    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("names the point and where it sits", () => {
    mount(2);

    expect(screen.getByRole("heading", { name: "Point 2 of 3" })).toBeDefined();
    // the axes are named: "1,390, 600" read as three numbers once a thousands comma came in
    expect(screen.getByText("x 30 · y 40")).toBeDefined();
  });

  it("edits the label as one history step: begin on focus, text on input, end on blur", () => {
    const actions = mount(2);
    const field = screen.getByRole("textbox", { name: "What to do here" });

    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "camp site" } });
    fireEvent.blur(field);

    expect(actions.beginEdit).toHaveBeenCalled();
    expect(actions.setText).toHaveBeenCalledWith(2, "camp site");
    expect(actions.endEdit).toHaveBeenCalled();
  });

  it("offers the colours by name and marks the point's own", async () => {
    const user = userEvent.setup();
    const actions = mount(2);

    expect(screen.getByRole("button", { name: "Blue" }).getAttribute("aria-pressed")).toBe("true");
    expect(
      screen.getByRole("button", { name: "Same as the route" }).getAttribute("aria-pressed"),
    ).toBe("false");

    await user.click(screen.getByRole("button", { name: "Same as the route" }));
    expect(actions.setColor).toHaveBeenCalledWith(2, null);
  });

  it("moves the point, and cannot move the first one earlier", async () => {
    const user = userEvent.setup();
    const actions = mount(1);

    expect(screen.getByRole("button", { name: "Move earlier" }).hasAttribute("disabled")).toBe(
      true,
    );
    await user.click(screen.getByRole("button", { name: "Move later" }));
    expect(actions.moveMarkerTo).toHaveBeenCalledWith(1, 1);
  });

  it("deletes the point, and closes by deselecting", async () => {
    const user = userEvent.setup();
    const actions = mount(3);

    await user.click(screen.getByRole("button", { name: "Delete point" }));
    expect(actions.deleteMarker).toHaveBeenCalledWith(3);
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(actions.select).toHaveBeenCalledWith(null);
  });

  it("offers the quest icons, marks the point's own, and changes it", async () => {
    const user = userEvent.setup();
    const actions = stubActions();
    render(
      <EditorWrap
        state={stubState({
          markers: [{ id: 7, x: 0, y: 0, text: "", icon: "main" }],
          selectedId: 7,
        })}
        actions={actions}
      >
        <Inspector />
      </EditorWrap>,
    );
    const pressed = (name: string) =>
      screen.getByRole("button", { name }).getAttribute("aria-pressed");

    expect([pressed("None"), pressed("Main quest"), pressed("Side quest")]).toEqual([
      "false",
      "true",
      "false",
    ]);
    await user.click(screen.getByRole("button", { name: "Side quest" }));
    expect(actions.setIcon).toHaveBeenLastCalledWith(7, "side");
    await user.click(screen.getByRole("button", { name: "None" }));
    expect(actions.setIcon).toHaveBeenLastCalledWith(7, null);
  });
});
