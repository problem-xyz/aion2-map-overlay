import { fireEvent, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EditorActions } from "../EditorContext";

import { useEditorHotkeys } from "./useEditorHotkeys";

/** Only the handlers the hotkeys reach; the rest of the context is not their business. */
function stubActions() {
  return {
    save: vi.fn(() => Promise.resolve("route")),
    undo: vi.fn(),
    redo: vi.fn(),
    select: vi.fn(),
    deleteMarker: vi.fn(),
    setColor: vi.fn(),
  };
}

function mount(selectedId: number | null = null) {
  const actions = stubActions();
  renderHook(() => useEditorHotkeys(actions as unknown as EditorActions, selectedId));
  return actions;
}

function textField(): HTMLInputElement {
  const input = document.createElement("input");
  document.body.append(input);
  input.focus();
  return input;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("useEditorHotkeys: Ctrl+S", () => {
  it("saves with nothing focused", () => {
    const actions = mount();

    const allowed = fireEvent.keyDown(document.body, { key: "s", ctrlKey: true });

    expect(actions.save).toHaveBeenCalledTimes(1);
    expect(allowed).toBe(false); // the browser's own "save page" must not open
  });

  it("saves while the caret is in a text field", () => {
    const actions = mount();
    const input = textField();

    const allowed = fireEvent.keyDown(input, { key: "s", ctrlKey: true });

    expect(actions.save).toHaveBeenCalledTimes(1);
    expect(allowed).toBe(false);
    expect(document.activeElement).toBe(input); // typing carries on after the save
  });

  it("answers Cmd+S the same way", () => {
    const actions = mount();

    fireEvent.keyDown(textField(), { key: "S", metaKey: true });

    expect(actions.save).toHaveBeenCalledTimes(1);
  });
});

describe("useEditorHotkeys: inside a text field", () => {
  it("leaves undo and redo to the field", () => {
    const actions = mount();
    const input = textField();

    expect(fireEvent.keyDown(input, { key: "z", ctrlKey: true })).toBe(true);
    expect(fireEvent.keyDown(input, { key: "y", ctrlKey: true })).toBe(true);

    expect(actions.undo).not.toHaveBeenCalled();
    expect(actions.redo).not.toHaveBeenCalled();
  });

  it("leaves Backspace and the digits to the field", () => {
    const actions = mount(7);
    const input = textField();

    fireEvent.keyDown(input, { key: "Backspace" });
    fireEvent.keyDown(input, { key: "3" });

    expect(actions.deleteMarker).not.toHaveBeenCalled();
    expect(actions.setColor).not.toHaveBeenCalled();
  });

  it("still lets Esc leave the field and drop the selection", () => {
    const actions = mount(7);
    const input = textField();

    fireEvent.keyDown(input, { key: "Escape" });

    expect(actions.select).toHaveBeenCalledWith(null);
    expect(document.activeElement).not.toBe(input);
  });
});
