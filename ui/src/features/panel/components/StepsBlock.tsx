import type { SettingsSchema } from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import Card from "@/shared/ui/Card";
import SettingSlider from "@/shared/ui/SettingSlider";
import Switch from "@/shared/ui/Switch";

export interface StepsBlockProps {
  pinned: boolean;
  /** settings.steps_scale: the zoom of the checklist's type and of its size with it. */
  scale: number;
  /** getState's settingsSchema, for the zoom's range. */
  schema: SettingsSchema | undefined;
  onPin: (pinned: boolean) => void;
  onScale: (scale: number) => void;
}

/**
 * The checklist's settings, in the Settings section. It is switched on and off from the run row,
 * beside Start, as the arrows are; what is left here is how it sits over the game.
 */
export default function StepsBlock({ pinned, scale, schema, onPin, onScale }: StepsBlockProps) {
  const { t, format } = useI18n();
  return (
    <Card title={t("panel.steps.title")}>
      <Switch
        checked={pinned}
        onChange={onPin}
        label={t("panel.steps.pin")}
        hint={t("panel.steps.pinHint")}
      />
      {/* The zoom, 50% to 150%: the type, and the size the user dragged the checklist to with it */}
      <SettingSlider
        name="steps_scale"
        schema={schema}
        label={t("panel.steps.sizeLabel")}
        value={scale}
        format={(v) => format.percent(v)}
        tip={t("panel.steps.sizeTip")}
        onChange={onScale}
      />
    </Card>
  );
}
