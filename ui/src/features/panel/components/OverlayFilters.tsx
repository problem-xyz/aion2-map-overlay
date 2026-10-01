import { useI18n, type MessageKey } from "@/shared/i18n";
import MarkIcon from "@/shared/ui/MarkIcon";
import type { ObjectIconName } from "@/shared/ui/markIcons";

export interface OverlayFiltersProps {
  /** The map's hidden cubes over the game: settings.show_cubes. */
  cubes: boolean;
  /** The route's points on Empyrean Traces, the feathers: settings.route_traces. */
  traces: boolean;
  /** The route's points on sealed dungeons: settings.route_seals. */
  seals: boolean;
  onCubes: (on: boolean) => void;
  onTraces: (on: boolean) => void;
  onSeals: (on: boolean) => void;
}

interface Filter {
  icon: ObjectIconName;
  label: MessageKey;
  short: MessageKey;
  on: boolean;
  onChange: (on: boolean) => void;
}

/**
 * What of the map's objects the overlay deals with, in a row of its own under Start: the cubes it
 * draws, and the feathers and the sealed dungeons a route may pass through. The same quick slots
 * as the run row, each with the game's own mark for what it switches.
 */
export default function OverlayFilters({
  cubes,
  traces,
  seals,
  onCubes,
  onTraces,
  onSeals,
}: OverlayFiltersProps) {
  const { t } = useI18n();
  const filters: Filter[] = [
    {
      icon: "cube",
      label: "panel.filters.cubes",
      short: "panel.filters.cubesShort",
      on: cubes,
      onChange: onCubes,
    },
    {
      icon: "trace",
      label: "panel.filters.traces",
      short: "panel.filters.tracesShort",
      on: traces,
      onChange: onTraces,
    },
    {
      icon: "seal",
      label: "panel.filters.seals",
      short: "panel.filters.sealsShort",
      on: seals,
      onChange: onSeals,
    },
  ];
  return (
    <div className="pn-filters" role="group" aria-label={t("panel.filters.label")}>
      {filters.map((f) => (
        <label key={f.icon} className="pn-chip" title={t(f.label)}>
          <input
            type="checkbox"
            checked={f.on}
            onChange={(e) => f.onChange(e.target.checked)}
            aria-label={t(f.label)}
          />
          <MarkIcon name={f.icon} className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t(f.short)}
          </span>
        </label>
      ))}
    </div>
  );
}
