import { useId } from "react";

import type { BackendApi } from "@/shared/backend/api";
import type { Settings, TimersState, TimerSignal } from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import Card from "@/shared/ui/Card";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";
import SettingSlider from "@/shared/ui/SettingSlider";
import Switch from "@/shared/ui/Switch";
import { REALM_HUES } from "@/shared/ui/timerMarks";

import { scheduleDate } from "../lib/format";
import { regionName, timerName } from "../lib/names";

import DropMark from "./DropMark";
import EventSettings, { LEADS } from "./EventSettings";

type Change = <K extends keyof Settings>(key: K, value: Settings[K]) => void;

export interface TimersSettingsProps {
  timers: TimersState;
  settings: Settings;
  schema: Parameters<typeof SettingSlider>[0]["schema"];
  api: BackendApi;
  onChange: Change;
}

/** The column heads of a group of event rows: said once, over the rows they name. */
function Heads() {
  const { t } = useI18n();
  return (
    <div className="tm-set-heads" aria-hidden="true">
      <span>{t("timers.settings.lead")}</span>
      <span>{t("timers.settings.shown")}</span>
    </div>
  );
}

/**
 * The timers' settings: the server, the sound and the clock first, then every event's own
 * choices, grouped as the schedule's filters group them, and the world bosses as one row for all
 * of them with the bosses to put on the plaque below it.
 */
export default function TimersSettings({
  timers,
  settings,
  schema,
  api,
  onChange,
}: TimersSettingsProps) {
  const { t, locale } = useI18n();
  const serverId = useId();
  const region = timers.regions.find((r) => r.id === timers.region);

  const group = (kind: "event" | "abyss" | "reset") =>
    timers.events.filter((e) =>
      kind === "event"
        ? e.kind === "event"
        : kind === "reset"
          ? e.kind === "reset"
          : e.kind === "boss",
    );
  const eventRows = (kind: "event" | "abyss" | "reset") =>
    group(kind).map((e) => (
      <EventSettings
        key={e.id}
        icon={e.icon}
        name={timerName(e, t)}
        shown={e.shown}
        lead={e.lead}
        signal={e.signal}
        onShown={(shown) => api.setTimerEvent(e.id, { shown })}
        onLead={(lead) => api.setTimerEvent(e.id, { lead })}
        onSignal={(signal) => api.setTimerEvent(e.id, { signal })}
        onPreview={() => api.previewTimerSignal(e.id)}
      />
    ));
  const section = (title: string, rows: React.ReactNode[], hue?: string) =>
    rows.length ? (
      <section className="tm-set-group">
        <h3 className="tm-set-title" style={hue ? { color: hue } : undefined}>
          {title}
        </h3>
        <div className="ui-frame tm-set-card">
          <Heads />
          <ul className="tm-set-list">{rows}</ul>
        </div>
      </section>
    ) : null;

  const shownWorld = new Set(settings.timers_world_shown);
  // the bosses worth the trip for a painting: one chip puts them all on the plaque, or takes them off
  const prized = timers.bosses.filter((b) => b.drops.includes("painting")).map((b) => b.id);
  const allPrized = prized.length > 0 && prized.every((id) => shownWorld.has(id));
  const worldSignal: TimerSignal = settings.timers_world_signal;
  const updated = scheduleDate(timers.updatedAt, locale);

  return (
    <div className="tm-settings">
      <Card title={t("timers.settings.general")}>
        <div className="ui-field">
          <div className="ui-field-head">
            <label htmlFor={serverId} className="ui-field-label">
              {t("timers.settings.server")}
            </label>
          </div>
          <select
            id={serverId}
            className="tm-select"
            value={timers.regionGuessed ? "" : timers.region}
            onChange={(e) => onChange("timers_region", e.target.value)}
          >
            <option value="">
              {t("timers.settings.serverGuessed", {
                label: region ? regionName(region, t) : timers.region,
              })}
            </option>
            {timers.regions.map((r) => (
              <option key={r.id} value={r.id}>
                {regionName(r, t)}
              </option>
            ))}
          </select>
        </div>
        {timers.serverGroups.length ? (
          <Segmented
            label={t("timers.settings.group")}
            value={timers.serverGroup ?? ""}
            options={[
              { value: "", label: t("timers.settings.groupAll") },
              ...timers.serverGroups.map((g) => ({
                value: g,
                label: t("timers.settings.groupN", { n: g }),
              })),
            ]}
            onChange={(v) => onChange("timers_server_group", v)}
          />
        ) : null}
        <Switch
          checked={settings.timers_sound}
          onChange={(on) => onChange("timers_sound", on)}
          label={t("timers.settings.sound")}
        />
        <div className="tm-volume">
          <SettingSlider
            name="timers_volume"
            schema={schema}
            label={t("timers.settings.volume")}
            value={settings.timers_volume}
            format={(v) => `${Math.round(v * 100)}%`}
            onChange={(v) => onChange("timers_volume", v)}
          />
          <IconButton
            className="btn-small ghost tm-set-play"
            label={t("timers.settings.test")}
            icon={<Icon name="play" />}
            onClick={() => api.previewTimerSignal("")}
          />
        </div>
        <Switch
          checked={settings.timers_clock_12h}
          onChange={(on) => onChange("timers_clock_12h", on)}
          label={t("timers.settings.clock12")}
        />
        <Switch
          checked={settings.timers_fetch}
          onChange={(on) => onChange("timers_fetch", on)}
          label={t("timers.settings.fetch")}
          hint={t("timers.settings.fetchHint")}
        />
        <div className="tm-fetch">
          <span>{t("timers.settings.schedule", { date: updated })}</span>
          <button
            type="button"
            className="btn-small"
            disabled={timers.fetching}
            onClick={() => api.refreshTimersData()}
          >
            {timers.fetching ? t("timers.settings.refreshing") : t("timers.settings.refresh")}
          </button>
        </div>
      </Card>

      {section(t("timers.settings.events"), eventRows("event"))}
      {section(t("timers.settings.abyss"), eventRows("abyss"), REALM_HUES.abyss)}
      {timers.bosses.length ? (
        <section className="tm-set-group">
          <h3 className="tm-set-title" style={{ color: REALM_HUES.world }}>
            {t("timers.settings.world")}
          </h3>
          <div className="ui-frame tm-set-card">
            <Heads />
            <ul className="tm-set-list">
              <EventSettings
                icon="demon"
                name={t("timers.settings.allWorld")}
                shown={shownWorld.size > 0}
                lead={
                  LEADS.includes(settings.timers_world_lead as (typeof LEADS)[number])
                    ? settings.timers_world_lead
                    : 5
                }
                signal={worldSignal}
                onShown={(on) => api.setTimersWorldShown(on ? timers.bosses.map((b) => b.id) : [])}
                onLead={(lead) => onChange("timers_world_lead", lead)}
                onSignal={(signal) => onChange("timers_world_signal", signal)}
                onPreview={() => api.previewTimerSignal(timers.bosses[0]?.id ?? "")}
              />
            </ul>
            <p className="tm-set-note">{t("timers.settings.worldNote")}</p>
            <div className="tm-chips">
              {prized.length ? (
                <button
                  type="button"
                  className={`tm-chip tm-chip-drop${allPrized ? " on" : ""}`}
                  aria-pressed={allPrized}
                  onClick={() =>
                    api.setTimersWorldShown(
                      allPrized
                        ? settings.timers_world_shown.filter((id) => !prized.includes(id))
                        : [...new Set([...settings.timers_world_shown, ...prized])],
                    )
                  }
                >
                  <span className="tm-name-line">
                    {/* the chip says it in words; the mark is only its picture */}
                    <span aria-hidden="true">
                      <DropMark drops={["painting"]} />
                    </span>
                    <span>{t("timers.settings.withDrop")}</span>
                  </span>
                </button>
              ) : null}
              {timers.bosses.map((b) => {
                const on = shownWorld.has(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    className={`tm-chip${on ? " on" : ""}`}
                    aria-pressed={on}
                    onClick={() =>
                      api.setTimersWorldShown(
                        on
                          ? settings.timers_world_shown.filter((id) => id !== b.id)
                          : [...settings.timers_world_shown, b.id],
                      )
                    }
                  >
                    <span className="tm-name-line">
                      <span>{b.name}</span>
                      <DropMark drops={b.drops} />
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}
      {section(t("timers.settings.resets"), eventRows("reset"))}
    </div>
  );
}
