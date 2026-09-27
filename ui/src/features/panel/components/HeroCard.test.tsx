/**
 * The active route's card: how far along, what it is called, what comes next.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ProgressState, RouteInfo } from "@/shared/backend/contract";
import { I18nProvider } from "@/shared/i18n";

import HeroCard from "./HeroCard";

const ROUTE: RouteInfo = {
  id: "loop",
  label: "Altgard loop",
  map: "altgard",
  mapLabel: "Altgard",
  markers: 3,
  steps: 2,
  thumb: "",
};

function progress(done: number): ProgressState {
  return {
    done,
    total: 3,
    map: [4096, 4096],
    markers: [
      { n: 1, text: "Gate", color: "#f2b544" },
      { n: 2, text: "", color: "#f2b544" },
      { n: 3, text: "Boss", color: "#6ea8ff" },
    ],
  };
}

function mount(route: RouteInfo | undefined, done: number) {
  render(
    <I18nProvider initial="en">
      <HeroCard
        route={route}
        progress={progress(done)}
        region={{ left: 0, top: 0, width: 800, height: 600 }}
      />
    </I18nProvider>,
  );
}

describe("HeroCard", () => {
  it("names the route and the point that comes next", () => {
    mount(ROUTE, 0);

    expect(screen.getByRole("heading", { name: "Altgard loop" })).toBeDefined();
    expect(screen.getByText("Gate")).toBeDefined();
    expect(screen.getByText(/map area 800 × 600/)).toBeDefined();
  });

  it("gives an unlabelled next point its number", () => {
    mount(ROUTE, 1);

    expect(screen.getByText("Point 2")).toBeDefined();
  });

  it("says the route is complete once every point is passed", () => {
    mount(ROUTE, 3);

    expect(screen.getByText("Route complete")).toBeDefined();
  });

  it("asks for a route when none is chosen", () => {
    mount(undefined, 0);

    expect(screen.getByRole("heading", { name: "No route chosen" })).toBeDefined();
  });
});
