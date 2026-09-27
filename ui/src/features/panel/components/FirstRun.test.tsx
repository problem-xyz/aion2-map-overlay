/** The first-run card: the two steps to a route on the game map, and the one button it needs. */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import FirstRun from "./FirstRun";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount() {
  const onDraw = vi.fn();
  render(
    <I18nProvider initial="en">
      <FirstRun onDraw={onDraw} />
    </I18nProvider>,
  );
  return onDraw;
}

describe("FirstRun", () => {
  it("names the two steps in order, with the borderless reminder", () => {
    mount();

    expect(screen.getByRole("heading", { name: en("panel.firstRun.title") })).toBeDefined();
    const steps = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(steps).toHaveLength(2);
    expect(steps[0]).toContain(en("panel.firstRun.route"));
    expect(steps[1]).toContain(en("panel.firstRun.start"));
    expect(screen.getByText(en("panel.status.fullscreenHint"))).toBeDefined();
  });

  it("opens the editor from the first step", async () => {
    const user = userEvent.setup();
    const onDraw = mount();

    await user.click(screen.getByRole("button", { name: en("panel.firstRun.routeAction") }));

    expect(onDraw).toHaveBeenCalledTimes(1);
  });

  it("sends nobody off to select the map area: the first Start asks for it", () => {
    mount();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
