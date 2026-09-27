/**
 * The capture area line. What is pinned is that the origin reads as a pair: with the thousands
 * separator a region on a second monitor read "from 1,280, 0", which looks like three numbers.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import Region from "./Region";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

describe("Region", () => {
  it("writes the origin as two numbers, not three", () => {
    render(
      <I18nProvider initial="en">
        <Region
          region={{ left: 1280, top: 0, width: 1920, height: 1080 }}
          onSelect={vi.fn()}
          onReset={vi.fn()}
        />
      </I18nProvider>,
    );

    const expected = en("panel.region.origin").replace("{left}", "1280").replace("{top}", "0");
    expect(screen.getByText(expected)).toBeDefined();
  });

  it("offers a reset only once there is an area to forget", () => {
    const onReset = vi.fn();
    const { rerender } = render(
      <I18nProvider initial="en">
        <Region region={null} onSelect={vi.fn()} onReset={onReset} />
      </I18nProvider>,
    );
    expect(screen.queryByRole("button", { name: en("panel.region.reset") })).toBeNull();

    rerender(
      <I18nProvider initial="en">
        <Region
          region={{ left: 0, top: 0, width: 800, height: 600 }}
          onSelect={vi.fn()}
          onReset={onReset}
        />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: en("panel.region.reset") }));
    expect(onReset).toHaveBeenCalledOnce();
  });
});
