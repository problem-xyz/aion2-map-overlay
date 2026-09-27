/**
 * The mock's scenarios: what the address asks for, and the state each one hands the page.
 */

import { describe, expect, it } from "vitest";

import { makeState, MOCK_ROUTE } from "./mockState";
import { applyScenario, readScenario, scenarioNotices } from "./scenarios";

function boot(search: string) {
  const state = makeState();
  const doc = structuredClone(MOCK_ROUTE);
  const scenario = readScenario(search);
  applyScenario(state, doc, scenario);
  return { state, doc, scenario };
}

describe("readScenario", () => {
  it("falls back to typical, and ignores values it does not know", () => {
    const s = readScenario("?scenario=nope&update=later&size=xl&steps=-1");

    expect(s.name).toBe("typical");
    expect(s.update).toBeNull();
    expect(s.size).toBeNull();
    expect(s.steps).toBeNull();
  });

  it("reads every parameter", () => {
    const s = readScenario("?scenario=steps&steps=100&long=1&size=l&pinned=0&lang=ru&bg=forest");

    expect(s).toMatchObject({
      name: "steps",
      steps: 100,
      long: true,
      size: "l",
      pinned: false,
      lang: "ru",
      bg: "forest",
    });
  });
});

describe("applyScenario", () => {
  it("empty: no routes, no map area, both maps still being cut", () => {
    const { state, doc } = boot("?scenario=empty");

    expect(state.routes).toEqual([]);
    expect(state.route).toBeNull();
    expect(state.region).toBeNull();
    expect(state.tilesBusy).toEqual(state.maps.map((m) => m.id));
    expect(doc.markers).toEqual([]);
  });

  it("many: 25 routes, the current one 96 points long in the editor and the progress alike", () => {
    const { state, doc } = boot("?scenario=many");

    expect(state.routes).toHaveLength(25);
    expect(doc.markers).toHaveLength(96);
    expect(state.progress.total).toBe(96);
    expect(state.routes.find((r) => r.id === state.route)?.markers).toBe(96);
  });

  it("progress: 7 of 96 done", () => {
    const { state } = boot("?scenario=progress");

    expect(state.progress).toMatchObject({ done: 7, total: 96 });
  });

  it("steps: as many points as asked for, long labels when asked", () => {
    expect(boot("?scenario=steps&steps=0").state.progress.markers).toHaveLength(0);
    const { state } = boot("?scenario=steps&steps=100&long=1");

    expect(state.progress.markers).toHaveLength(100);
    expect(state.progress.markers[0]?.text.length).toBeGreaterThanOrEqual(120);
  });

  it("update: the banner in the phase asked for, with a version where the phase has one", () => {
    expect(boot("?scenario=update").state.update).toMatchObject({ phase: "available" });
    expect(boot("?scenario=update&update=downloading").state.update).toMatchObject({
      phase: "downloading",
      progress: 40,
    });
    expect(boot("?scenario=update&update=checking").state.update).toEqual({ phase: "checking" });
  });

  it("errors: a route whose map this version lacks, and a toast of every level", () => {
    const { state, scenario } = boot("?scenario=errors");

    expect(state.routes.some((r) => !r.mapLabel)).toBe(true);
    expect(new Set(scenarioNotices(scenario).map((n) => n.level))).toEqual(
      new Set(["info", "warning", "error"]),
    );
  });

  it("applies the plaque, language and tile parameters over any scenario", () => {
    const { state } = boot("?scenario=typical&size=s&pinned=0&lang=ru&tiles=busy");

    expect(state.steps).toMatchObject({ size: "s", pinned: false });
    expect(state.settings.language).toBe("ru");
    expect(state.maps.every((m) => !m.tiles.ready)).toBe(true);
  });
});
