import { useCallback, useMemo, useState } from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { type MessageKey, useI18n } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";
import Sheen from "@/shared/ui/Sheen";

import ScheduleView from "./components/ScheduleView";
import TimersHero from "./components/TimersHero";
import TimersSettings from "./components/TimersSettings";
import { useNow } from "./hooks/useNow";
import { byTime, type Filter, type Realm, timersAt } from "./lib/model";
import "./timers.css";

type View = "schedule" | "settings";
const VIEWS: readonly { id: View; label: MessageKey; icon: IconName }[] = [
  { id: "schedule", label: "timers.tabs.schedule", icon: "clock" },
  { id: "settings", label: "timers.tabs.settings", icon: "gear" },
];

function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const stored = window.localStorage.getItem(key) ?? "";
    return allowed.find((x) => x === stored) ?? fallback;
  } catch {
    return fallback;
  }
}

function useRemembered<T extends string>(key: string, allowed: readonly T[], fallback: T) {
  const [value, setValue] = useState<T>(() => remembered(key, allowed, fallback));
  const set = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next);
      } catch {
        /* private mode: the choice lasts until the panel closes */
      }
    },
    [key],
  );
  return [value, set] as const;
}

/**
 * The timers tool of the control panel: the leading card, then the schedule or the settings.
 *
 * The countdowns tick here, once a second, from the moments Python sent; Python itself only
 * sends again when what it says changes.
 */
export default function TimersPage() {
  const api = useApi();
  const { t } = useI18n();
  const changeSetting = useSettingsPatch();
  const timers = useBackendState<AppState | null, AppState["timers"]>((s) => s?.timers);
  const settings = useBackendState<AppState | null, AppState["settings"] | undefined>(
    (s) => s?.settings,
  );
  const schema = useBackendState<AppState | null, AppState["settingsSchema"]>(
    (s) => s?.settingsSchema,
  );
  const [view, setView] = useRemembered<View>(
    "mo.timers.view",
    ["schedule", "settings"],
    "schedule",
  );
  const [filter, setFilter] = useRemembered<Filter>(
    "mo.timers.filter",
    ["all", "event", "boss"],
    "all",
  );
  const [realm, setRealm] = useRemembered<Realm>(
    "mo.timers.realm",
    ["all", "world", "abyss"],
    "all",
  );
  const now = useNow(1000);

  const all = useMemo(
    () => (timers && settings ? timersAt(timers, now, settings.timers_world_lead) : []),
    [timers, settings, now],
  );

  if (!api || !settings) return null;
  if (!timers) return <p className="muted tm-empty">{t("timers.empty")}</p>;

  const twelve = settings.timers_clock_12h;
  const resets = all.filter((x) => x.kind === "reset");
  const lead =
    all
      .filter((x) => x.shown && x.kind !== "reset")
      .sort(byTime)
      .find(() => true) ?? null;

  return (
    <div className="tm-page">
      <TimersHero lead={lead} resets={resets} now={now} twelve={twelve} />

      <div role="tablist" aria-label={t("timers.label")} className="pn-menu tm-menu">
        {VIEWS.map(({ id, label, icon }) => {
          const on = id === view;
          return (
            <button
              key={id}
              id={`tm-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={on}
              aria-controls={`tm-view-${id}`}
              tabIndex={on ? 0 : -1}
              className={on ? "pn-tile on" : "pn-tile"}
              onClick={() => setView(id)}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                  e.preventDefault();
                  const next = id === "schedule" ? "settings" : "schedule";
                  setView(next);
                  document.getElementById(`tm-tab-${next}`)?.focus();
                }
              }}
            >
              {on ? <Sheen /> : null}
              <Icon name={icon} className="pn-tile-icon" />
              <span className="pn-tile-label">{t(label)}</span>
            </button>
          );
        })}
      </div>

      <div id={`tm-view-${view}`} role="tabpanel" aria-labelledby={`tm-tab-${view}`}>
        {view === "schedule" ? (
          <ScheduleView
            timers={all}
            now={now}
            twelve={twelve}
            filter={filter}
            realm={realm}
            onFilter={setFilter}
            onRealm={setRealm}
            bossesReadAt={timers.bossesReadAt}
            wrongCycle={timers.wrongCycle}
          />
        ) : (
          <TimersSettings
            timers={timers}
            settings={settings}
            schema={schema}
            api={api}
            onChange={changeSetting}
          />
        )}
      </div>
    </div>
  );
}
