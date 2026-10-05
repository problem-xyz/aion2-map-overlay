import { useMemo } from "react";

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
import { useRemembered } from "./hooks/useRemembered";
import { byTime, type Filter, type Realm, timersAt } from "./lib/model";
import "./timers.css";

type View = "schedule" | "settings";
const VIEWS: readonly { id: View; label: MessageKey; icon: IconName }[] = [
  { id: "schedule", label: "timers.tabs.schedule", icon: "clock" },
  { id: "settings", label: "timers.tabs.settings", icon: "gear" },
];

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
  const plaque = useBackendState<AppState | null, AppState["timersPlaque"]>((s) => s?.timersPlaque);
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

      {/* The plaque over the game and the reminders' sound: what is switched most, a click away */}
      <div className="tm-quick">
        <label className="pn-chip" title={t("timers.plaque.show")}>
          <input
            type="checkbox"
            checked={Boolean(plaque?.visible)}
            onChange={(e) => api.setTimersPlaqueVisible(e.target.checked)}
            aria-label={t("timers.plaque.show")}
          />
          <Icon name="list" className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("timers.plaque.show")}
          </span>
        </label>
        <label className="pn-chip" title={t("timers.settings.sound")}>
          <input
            type="checkbox"
            checked={settings.timers_sound}
            onChange={(e) => changeSetting("timers_sound", e.target.checked)}
            aria-label={t("timers.settings.sound")}
          />
          <Icon name="bell" className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("timers.plaque.sound")}
          </span>
        </label>
        <button type="button" className="pn-chip" onClick={() => api.openTimersTimeline()}>
          <Icon name="timeline" className="pn-chip-icon" />
          <span className="pn-chip-label">{t("timers.timeline.open")}</span>
        </button>
      </div>

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
            onSettings={() => setView("settings")}
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
