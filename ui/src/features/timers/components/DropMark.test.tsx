/** The drop mark: named for a kind it knows, nothing for one only a newer app knows. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import DropMark from "./DropMark";

const mount = (drops: string[] | undefined) =>
  render(
    <I18nProvider initial="en">
      <DropMark drops={drops} />
    </I18nProvider>,
  );

describe("DropMark", () => {
  it("names a painting for the screen reader and the pointer alike", () => {
    mount(["relic", "painting"]);
    expect(screen.getByText("Drops a painting")).toBeDefined();
    expect(screen.getByTitle("Drops a painting")).toBeDefined();
  });

  it("draws nothing for no drops or a kind it does not know", () => {
    const { container } = mount(["relic"]);
    expect(container.textContent).toBe("");
    mount(undefined);
    expect(screen.queryByText("Drops a painting")).toBeNull();
  });
});
