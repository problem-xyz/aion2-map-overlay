import { type CSSProperties, type PointerEvent, useEffect, useMemo, useRef, useState } from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { type MessageKey, useI18n } from "@/shared/i18n";
import Segmented from "@/shared/ui/Segmented";
import TimerMark from "@/shared/ui/TimerMark";
import { timerHue } from "@/shared/ui/timerMarks";

import DropMark from "../components/DropMark";
import { useNow } from "../hooks/useNow";
import { useRemembered } from "../hooks/useRemembered";
import { clock, day } from "../lib/format";
import { type Filter, type Realm, timersAt } from "../lib/model";
import { timerName } from "../lib/names";
import {
  at,
  type Bar,
  type Hours,
  type Lane,
  lanes,
  resets,
  ticks,
  timelineSpan,
} from "../lib/timeline";
import "../timers.css";
import "./timeline.css";

const GROUPS: Record<Lane["group"], MessageKey> = {
  event: "timers.filter.event",
  abyss: "timers.filter.abyss",
  world: "timers.filter.world",
};

const pct = (fraction: number) => `${(fraction * 100).toFixed(3)}%`;

interface Tip {
  text: string;
  x: number;
  y: number;
}

/**
 * The day timeline, in a window of its own: a lane per event and per world boss across one or two
 * days, the resets drawn through them all, and a line at now.
 *
 * It is read at a glance, not worked through: the bars take no focus and say what they are on
 * hover. What the chart shows is also a table, read out instead of it.
 */
export default function TimelinePage() {
  const api = useApi();
  const { t, locale } = useI18n();
  const timers = useBackendState<AppState | null, AppState["timers"]>((s) => s?.timers);
  const settings = useBackendState<AppState | null, AppState["settings"] | undefined>(
    (s) => s?.settings,
  );
  const [chosenFilter, setFilter] = useRemembered<Filter>(
    "mo.timeline.filter",
    ["all", "event", "boss"],
    "all",
  );
  const [chosenRealm, setRealm] = useRemembered<Realm>(
    "mo.timeline.realm",
    ["all", "world", "abyss"],
    "all",
  );
  const [hours, setHours] = useRemembered<"24" | "48">("mo.timeline.hours", ["24", "48"], "24");
  const span_h = Number(hours) as Hours;
  // the now line moves a sixth of a pixel a minute on a wide window: no need to redraw every second
  const now = useNow(15_000);
  const [tip, setTip] = useState<Tip | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) api?.closeTimersTimeline();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [api]);

  const twelve = settings?.timers_clock_12h ?? false;
  const all = useMemo(
    () => (timers && settings ? timersAt(timers, now, settings.timers_world_lead) : []),
    [timers, settings, now],
  );
  const span = useMemo(() => timelineSpan(now, span_h), [now, span_h]);
  // no boss at all (switched off app-wide): nothing for the filter to tell apart
  const hasBosses = all.some((x) => x.kind === "boss");
  const filter: Filter = hasBosses ? chosenFilter : "all";
  // no world bosses: no realm to choose between
  const hasWorld = Boolean(timers?.bosses.length);
  const realm: Realm = hasWorld ? chosenRealm : "all";
  const rows = useMemo(() => lanes(all, now, span, filter, realm), [all, now, span, filter, realm]);
  const lines = useMemo(() => resets(all, span), [all, span]);
  const marks = useMemo(() => ticks(span, span_h), [span, span_h]);
  const lanesRef = useRef(rows);
  lanesRef.current = rows;

  if (!api || !settings) return null;

  const when = (lane: Lane, b: Bar): string => {
    const from = clock(b.start, locale, twelve);
    const time =
      b.point || lane.group === "world" ? from : `${from}–${clock(b.end, locale, twelve)}`;
    const parts = [`${day(b.start, now, locale, t)} ${time}`];
    if (b.estimated) parts.push(t("timers.status.estimated"));
    return parts.join(" · ");
  };
  const tipFor = (lane: Lane, b: Bar) => `${timerName(lane.timer, t)} · ${when(lane, b)}`;

  // One handler for every bar: a chart of two days holds several hundred of them
  const onPointer = (e: PointerEvent<HTMLDivElement>) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>("[data-bar]");
    if (!el) {
      if (tip) setTip(null);
      return;
    }
    const [li = -1, bi = -1] = (el.dataset.bar ?? "").split(":").map(Number);
    const lane = lanesRef.current.at(li);
    const b = lane?.bars.at(bi);
    if (!lane || !b) return;
    setTip({ text: tipFor(lane, b), x: e.clientX, y: e.clientY });
  };

  const nowLeft = at(now, span);
  let lastGroup: Lane["group"] | null = null;

  return (
    <div className="tl-page">
      <header className="tl-head">
        <h1 className="tl-title">{t("timers.timeline.open")}</h1>
        <span className="tl-clock">{clock(now, locale, twelve)}</span>
        <div className="tl-controls">
          {hasBosses ? (
            <Segmented
              label={t("timers.filter.label")}
              labelHidden
              value={filter}
              options={[
                { value: "all", label: t("timers.filter.all") },
                { value: "event", label: t("timers.filter.event") },
                { value: "boss", label: t("timers.filter.boss") },
              ]}
              onChange={setFilter}
            />
          ) : null}
          {filter === "boss" && hasWorld ? (
            <Segmented
              label={t("timers.filter.realmLabel")}
              labelHidden
              value={realm}
              options={[
                { value: "all", label: t("timers.filter.realmAll") },
                { value: "world", label: t("timers.filter.world") },
                { value: "abyss", label: t("timers.filter.abyss") },
              ]}
              onChange={setRealm}
            />
          ) : null}
          <Segmented
            label={t("timers.timeline.span")}
            labelHidden
            value={hours}
            options={[
              { value: "24", label: t("timers.timeline.day") },
              { value: "48", label: t("timers.timeline.twoDays") },
            ]}
            onChange={setHours}
          />
        </div>
      </header>

      {!timers ? (
        <p className="muted tl-empty">{t("timers.empty")}</p>
      ) : rows.length === 0 ? (
        <p className="muted tl-empty">{t("timers.timeline.nothing")}</p>
      ) : (
        <div className="tl-chart" aria-hidden="true">
          <div className="tl-axis">
            <div className="tl-axis-scale">
              {marks
                // an hour's label makes way for now's
                .filter((m) => m.labelled && m.left < 0.985 && Math.abs(m.left - nowLeft) > 0.045)
                .map((m) => (
                  <span
                    key={m.at}
                    className={m.midnight ? "tl-hour midnight" : "tl-hour"}
                    style={{ left: pct(m.left) }}
                  >
                    {m.midnight ? day(m.at, now, locale, t) : clock(m.at, locale, twelve)}
                  </span>
                ))}
              {nowLeft >= 0 && nowLeft <= 1 ? (
                <span className="tl-now-label" style={{ left: pct(nowLeft) }}>
                  {t("timers.timeline.now")}
                </span>
              ) : null}
            </div>
          </div>

          <div className="tl-body" onPointerMove={onPointer} onPointerLeave={() => setTip(null)}>
            <div className="tl-grid">
              {marks.map((m) => (
                <i
                  key={m.at}
                  className={m.midnight ? "tl-tick midnight" : "tl-tick"}
                  style={{ left: pct(m.left) }}
                />
              ))}
              {lines.map((r) => (
                <i
                  key={r.at}
                  className={r.weekly ? "tl-reset weekly" : "tl-reset"}
                  style={{ left: pct(r.left) }}
                />
              ))}
              {nowLeft >= 0 && nowLeft <= 1 ? (
                <i className="tl-now" style={{ left: pct(nowLeft) }} />
              ) : null}
            </div>

            {rows.map((lane, li) => {
              const head = lane.group !== lastGroup && filter !== "event" ? lane.group : null;
              lastGroup = lane.group;
              const hue: CSSProperties = { "--tm-hue": timerHue(lane.timer.icon) };
              return (
                <div key={lane.timer.id} className="tl-lane-wrap">
                  {head ? <div className="tl-group">{t(GROUPS[head])}</div> : null}
                  <div className="tl-lane" style={hue}>
                    <div className="tl-label">
                      <TimerMark icon={lane.timer.icon} size="sm" />
                      <span className="tl-name">{timerName(lane.timer, t)}</span>
                      <DropMark drops={lane.timer.boss?.drops} />
                    </div>
                    <div className="tl-track">
                      {lane.bars.map((b, bi) => {
                        // a world boss is up for minutes: too short to read as a span
                        const point = b.point || lane.group === "world";
                        const cls = [
                          "tl-bar",
                          b.state,
                          point ? "point" : "",
                          b.estimated ? "estimated" : "",
                        ];
                        return (
                          <span
                            key={b.start}
                            data-bar={`${li}:${bi}`}
                            className={cls.filter(Boolean).join(" ")}
                            style={
                              point
                                ? { left: pct(b.left) }
                                : { left: pct(b.left), width: pct(b.width) }
                            }
                          />
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tip ? (
        <div className="tl-tip" role="presentation" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      ) : null}

      <table className="ui-sr-only">
        <caption>{t("timers.timeline.table")}</caption>
        <tbody>
          {rows.map((lane) => {
            const next = lane.bars.find((b) => b.state !== "past");
            return (
              <tr key={lane.timer.id}>
                <th scope="row">{timerName(lane.timer, t)}</th>
                <td>{next ? when(lane, next) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
