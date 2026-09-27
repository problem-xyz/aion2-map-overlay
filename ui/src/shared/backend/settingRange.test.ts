import { describe, expect, it } from "vitest";

import type { SettingsSchema } from "@/shared/backend/contract";

import { sliderRange } from "./settingRange";

const SCHEMA: SettingsSchema = {
  opacity: { type: "float", default: 0.85, min: 0.1, max: 1 },
  fps: { type: "int", default: 60, min: 30, max: 240 },
  flow_points: { type: "int", default: 200, min: 40, max: 2000 },
  reproj_thr: { type: "float", default: 4, min: 0.5, max: 20.5 },
  hold_frames: { type: "int", default: 8 },
  ratio: { type: "float", default: 0.75, min: 0.9, max: 0.5 },
};

describe("sliderRange", () => {
  it("takes the bounds from the schema and the step from the table", () => {
    expect(sliderRange(SCHEMA, "opacity")).toEqual({ min: 0.1, max: 1, step: 0.05 });
    expect(sliderRange(SCHEMA, "fps")).toEqual({ min: 30, max: 240, step: 5 });
  });

  it("follows the schema when Python moves a range", () => {
    const moved: SettingsSchema = { fps: { type: "int", default: 60, min: 60, max: 144 } };
    expect(sliderRange(moved, "fps")).toEqual({ min: 60, max: 144, step: 5 });
  });

  it("steps an integer the table does not list by one", () => {
    expect(sliderRange(SCHEMA, "flow_points")?.step).toBe(1);
  });

  it("steps any other number the table does not list by a hundredth of its range", () => {
    expect(sliderRange(SCHEMA, "reproj_thr")?.step).toBeCloseTo(0.2);
  });

  it("offers no range when there is no schema, no entry, no bounds or no width", () => {
    expect(sliderRange(undefined, "opacity")).toBeNull();
    expect(sliderRange(SCHEMA, "smoothing")).toBeNull();
    expect(sliderRange(SCHEMA, "hold_frames")).toBeNull();
    expect(sliderRange(SCHEMA, "ratio")).toBeNull();
  });
});
