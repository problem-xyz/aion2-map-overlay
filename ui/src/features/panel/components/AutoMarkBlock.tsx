import { useId } from "react";

import type { SettingsSchema } from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import SettingSlider from "@/shared/ui/SettingSlider";
import Switch from "@/shared/ui/Switch";

import Card from "./Card";

export interface AutoMarkBlockProps {
  /** settings.auto_progress: a point is ticked off once the player comes within the radius. */
  auto: boolean;
  /** settings.arrive_radius, a fraction of the map's width. */
  radius: number;
  /** The route's map size, to show the radius in map pixels; null without a route. */
  map: [number, number] | null;
  /** getState's settingsSchema, for the radius slider's range. */
  schema: SettingsSchema | undefined;
  onToggle: (auto: boolean) => void;
  onRadius: (radius: number) => void;
}

/**
 * Marking points by walking up to them: a card of its own with the radius under its switch,
 * where it used to be one switch among the progress card's rows and easy to miss.
 */
export default function AutoMarkBlock({
  auto,
  radius,
  map,
  schema,
  onToggle,
  onRadius,
}: AutoMarkBlockProps) {
  const { t, format } = useI18n();
  // The switch has no label of its own: the card's heading is its name, so it points at it.
  const headingId = useId();
  // Map pixels read better than a fraction: the same unit the route's own coordinates use
  const inPixels =
    map && map[0]
      ? t("panel.auto.radiusPx", { px: Math.round(radius * map[0]) })
      : format.percent(radius, 1);

  return (
    <Card
      title={t("panel.auto.title")}
      headingId={headingId}
      aside={<Switch checked={auto} onChange={onToggle} labelledBy={headingId} />}
    >
      {auto ? (
        <SettingSlider
          name="arrive_radius"
          schema={schema}
          label={t("panel.auto.radius")}
          value={radius}
          format={() => inPixels}
          hint={t("panel.auto.radiusHint")}
          onChange={onRadius}
        />
      ) : (
        <p className="muted pn-card-text">{t("panel.auto.off")}</p>
      )}
    </Card>
  );
}
