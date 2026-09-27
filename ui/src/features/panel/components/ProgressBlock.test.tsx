/**
 * The progress card always counts: no switch to turn it off. Its points stay a list of
 * checkboxes, one per marker, each with its icon.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProgressState } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";
import type { MarkIconName } from "@/shared/ui/markIcons";

import ProgressBlock from "./ProgressBlock";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

const PROGRESS: ProgressState = {
  done: 1,
  total: 3,
  map: [2048, 2048],
  markers: [
    { n: 1, text: "Start", color: "#ff0000" },
    { n: 2, text: "Middle", color: "#00ff00" },
    { n: 3, text: "End", color: "#0000ff" },
  ],
};

function mount(icons: (MarkIconName | null)[] = [], onSet = vi.fn()) {
  render(
    <I18nProvider initial="en">
      <ProgressBlock progress={PROGRESS} icons={icons} onSet={onSet} onReset={vi.fn()} />
    </I18nProvider>,
  );
  return onSet;
}

describe("ProgressBlock", () => {
  it("has no switch to turn progress off", () => {
    mount();

    expect(screen.getByRole("heading", { name: en("panel.progress.title") })).toBeDefined();
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("keeps the points a list of checkboxes, one per marker", () => {
    mount();
    expect(screen.getAllByRole("checkbox")).toHaveLength(PROGRESS.markers.length);
  });

  it("marks a point passed with its box", async () => {
    const user = userEvent.setup();
    const onSet = mount();

    await user.click(screen.getAllByRole("checkbox")[2] as HTMLElement);

    expect(onSet).toHaveBeenCalledWith(3);
  });

  it("draws a point's icon between its number and its label, and none where it has none", () => {
    mount(["questMain", null, "teleport"]);

    const rows = screen.getAllByRole("listitem");
    expect(rows.map((row) => row.querySelectorAll("svg").length)).toEqual([1, 0, 1]);
  });
});
