import type { Settings, SettingsSchema } from "@/shared/backend/contract";

/** The settings a slider can drive: the ones whose value is a number. */
export type NumericSetting = {
  [K in keyof Settings]: Settings[K] extends number ? K : never;
}[keyof Settings];

export interface SliderRange {
  min: number;
  max: number;
  step: number;
}

/**
 * How far one notch of a slider moves each setting.
 *
 * Steps are presentation and live here; the range they walk is not, and comes from Python. A
 * setting missing from this table still gets a slider: 1 for an integer, a hundredth of the
 * range for anything else.
 */
const STEPS: Partial<Record<NumericSetting, number>> = {
  opacity: 0.05,
  editor_opacity: 0.05,
  fps: 5,
  smoothing: 0.05,
  detect_interval: 0.1,
  min_inliers: 1,
  arrive_radius: 1 / 4096, // one map pixel on either map, both 4096 wide
  steps_scale: 0.05,
};

/**
 * The slider bounds for one setting, or null when the schema gives no usable range.
 *
 * Null rather than a guess: a backend from before api 4 sends no schema, and a range made up
 * here would be exactly the second copy of the ranges that the schema exists to remove.
 */
export function sliderRange(
  schema: SettingsSchema | undefined,
  name: NumericSetting,
): SliderRange | null {
  const field = schema?.[name];
  if (!field || field.min === undefined || field.max === undefined || field.max <= field.min) {
    return null;
  }
  const step = STEPS[name] ?? (field.type === "int" ? 1 : (field.max - field.min) / 100);
  return { min: field.min, max: field.max, step };
}
