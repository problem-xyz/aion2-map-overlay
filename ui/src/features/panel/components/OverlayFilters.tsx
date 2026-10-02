import { useI18n, type MessageKey } from "@/shared/i18n";
import MarkIcon from "@/shared/ui/MarkIcon";
import type { ObjectIconName } from "@/shared/ui/markIcons";

import ResourcesFilter from "./ResourcesFilter";

export interface OverlayFiltersProps {
  /** The map's hidden cubes over the game: settings.show_cubes. */
  cubes: boolean;
  /** The map's gathering points over the game: settings.show_resources. */
  resources: boolean;
  /** Which resources are drawn: settings.resources. */
  picked: readonly string[];
  /** The resources the list offers. */
  available: readonly string[];
  /** The route's points on Empyrean Traces, the feathers: settings.route_traces. */
  traces: boolean;
  /** The route's points on sealed dungeons: settings.route_seals. */
  seals: boolean;
  onCubes: (on: boolean) => void;
  onResources: (on: boolean) => void;
  onPick: (ids: string[]) => void;
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

function Chip({ filter }: { filter: Filter }) {
  const { t } = useI18n();
  return (
    <label className="pn-chip" title={t(filter.label)}>
      <input
        type="checkbox"
        checked={filter.on}
        onChange={(e) => filter.onChange(e.target.checked)}
        aria-label={t(filter.label)}
      />
      <MarkIcon name={filter.icon} className="pn-chip-icon" />
      <span className="pn-chip-label" aria-hidden="true">
        {t(filter.short)}
      </span>
    </label>
  );
}

/**
 * What of the map's objects the overlay deals with, in a row of its own under Start: the cubes and
 * the resources it draws, and the feathers and the sealed dungeons a route may pass through. The
 * same quick slots as the run row, each with the game's own mark for what it switches.
 */
export default function OverlayFilters({
  cubes,
  resources,
  picked,
  available,
  traces,
  seals,
  onCubes,
  onResources,
  onPick,
  onTraces,
  onSeals,
}: OverlayFiltersProps) {
  const { t } = useI18n();
  const route: Filter[] = [
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
      <Chip
        filter={{
          icon: "cube",
          label: "panel.filters.cubes",
          short: "panel.filters.cubesShort",
          on: cubes,
          onChange: onCubes,
        }}
      />
      <ResourcesFilter
        on={resources}
        picked={picked}
        available={available}
        onToggle={onResources}
        onPick={onPick}
      />
      {route.map((f) => (
        <Chip key={f.icon} filter={f} />
      ))}
    </div>
  );
}
