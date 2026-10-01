/**
 * The row of filters under Start: each slot switches its own setting and nothing else.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import OverlayFilters, { type OverlayFiltersProps } from "./OverlayFilters";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(props: Partial<OverlayFiltersProps> = {}) {
  const all: OverlayFiltersProps = {
    cubes: false,
    traces: true,
    seals: true,
    onCubes: vi.fn(),
    onTraces: vi.fn(),
    onSeals: vi.fn(),
    ...props,
  };
  render(
    <I18nProvider initial="en">
      <OverlayFilters {...all} />
    </I18nProvider>,
  );
  return all;
}

function box(key: string): HTMLInputElement {
  return screen.getByRole<HTMLInputElement>("checkbox", { name: en(key) });
}

describe("OverlayFilters", () => {
  it("shows each filter as it stands", () => {
    mount({ cubes: true, traces: false, seals: true });

    expect(box("panel.filters.cubes").checked).toBe(true);
    expect(box("panel.filters.traces").checked).toBe(false);
    expect(box("panel.filters.seals").checked).toBe(true);
  });

  it("switches the one filter clicked", () => {
    const props = mount();

    fireEvent.click(box("panel.filters.seals"));

    expect(props.onSeals).toHaveBeenCalledWith(false);
    expect(props.onCubes).not.toHaveBeenCalled();
    expect(props.onTraces).not.toHaveBeenCalled();
  });
});
