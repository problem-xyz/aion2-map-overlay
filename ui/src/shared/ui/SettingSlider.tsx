import type { SettingsSchema } from "@/shared/backend/contract";
import { type NumericSetting, sliderRange } from "@/shared/backend/settingRange";

import Slider, { type SliderProps } from "./Slider";

export interface SettingSliderProps extends Omit<SliderProps, "min" | "max" | "step"> {
  name: NumericSetting;
  schema: SettingsSchema | undefined;
}

/**
 * A Slider over one setting, bounded by the range Python enforces on it.
 *
 * With no range for the setting the control is left out: offering values the file may reject
 * would only have them clamped back behind the user's back.
 */
export default function SettingSlider({ name, schema, ...slider }: SettingSliderProps) {
  const range = sliderRange(schema, name);
  if (!range) return null;
  return <Slider {...slider} {...range} />;
}
