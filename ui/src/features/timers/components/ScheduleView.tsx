import { useI18n } from "@/shared/i18n";
import Segmented from "@/shared/ui/Segmented";

import { clock, day } from "../lib/format";
import { byTime, type Filter, passes, type Realm, type TimerNow } from "../lib/model";

import TimerRow from "./TimerRow";

/** World bosses shown outside their own tab: the soonest few, then a way to the rest. */
const WORLD_PREVIEW = 3;

export interface ScheduleViewProps {
  timers: TimerNow[];
  now: number;
  twelve: boolean;
  filter: Filter;
  realm: Realm;
  onFilter: (filter: Filter) => void;
  onRealm: (realm: Realm) => void;
  /** When the world bosses' list was read in the game; null with none for this region. */
  bossesReadAt: number | null;
  wrongCycle: string[];
  /** Where the timers are switched on and off: shown when a list has none switched on. */
  onSettings?: () => void;
}

/**
 * The schedule: every timer, soonest first, narrowed to events or bosses, and the bosses to the
 * world's or the Abyss's. The list carries no buttons; what each timer does is in Settings.
 */
export default function ScheduleView({
  timers,
  now,
  twelve,
  filter,
  realm,
  onFilter,
  onRealm,
  bossesReadAt,
  wrongCycle,
  onSettings,
}: ScheduleViewProps) {
  const { t, locale } = useI18n();
  const worldTab = filter === "boss" && realm === "world";
  // A list holds what the player follows. The world tab is the one place every world boss is
  // listed, the ones switched off greyed, so a boss can still be looked up there.
  const listed = timers
    .filter((x) => passes(x, filter, realm) && (x.shown || worldTab))
    .sort(byTime);
  const world = listed.filter((x) => x.source === "boss");
  const hidden = worldTab ? 0 : Math.max(0, world.length - WORLD_PREVIEW);
  const kept = new Set(world.slice(0, WORLD_PREVIEW).map((x) => x.id));
  const rows = worldTab ? listed : listed.filter((x) => x.source !== "boss" || kept.has(x.id));

  return (
    <div className="tm-schedule">
      <Segmented
        label={t("timers.filter.label")}
        labelHidden
        value={filter}
        options={[
          { value: "all", label: t("timers.filter.all") },
          { value: "event", label: t("timers.filter.event") },
          { value: "boss", label: t("timers.filter.boss") },
        ]}
        onChange={onFilter}
      />
      {filter === "boss" ? (
        <Segmented
          label={t("timers.filter.realmLabel")}
          labelHidden
          value={realm}
          options={[
            { value: "all", label: t("timers.filter.realmAll") },
            { value: "world", label: t("timers.filter.world") },
            { value: "abyss", label: t("timers.filter.abyss") },
          ]}
          onChange={onRealm}
        />
      ) : null}

      <div className="ui-frame tm-list-card">
        {world.length && bossesReadAt !== null ? (
          <p className="tm-list-note">
            {t("timers.world.listFrom", {
              time: clock(bossesReadAt, locale, twelve),
              day: day(bossesReadAt, now, locale, t),
            })}
          </p>
        ) : null}
        {rows.length ? (
          <ul className="tm-list">
            {rows.map((x) => (
              <TimerRow
                key={`${x.source}:${x.id}`}
                timer={x}
                now={now}
                twelve={twelve}
                wrongCycle={x.source === "boss" && wrongCycle.includes(x.id)}
                off={!x.shown}
              />
            ))}
          </ul>
        ) : (
          <div className="tm-list-empty">
            <p className="muted">{t("timers.list.noneOn")}</p>
            {onSettings ? (
              <button type="button" className="btn-small" onClick={onSettings}>
                {t("timers.list.toSettings")}
              </button>
            ) : null}
          </div>
        )}
        {hidden ? (
          <button
            type="button"
            className="tm-list-more"
            onClick={() => {
              onFilter("boss");
              onRealm("world");
            }}
          >
            {t("timers.world.more", { count: hidden })}
          </button>
        ) : null}
      </div>
    </div>
  );
}
