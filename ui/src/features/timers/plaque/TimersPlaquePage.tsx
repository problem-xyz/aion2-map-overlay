import {
  type CSSProperties,
  type PointerEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
} from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { TimersPlaqueData } from "@/shared/backend/contract";
import { useTimersPlaqueApi } from "@/shared/backend/hooks";
import { type MessageKey, useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import { REALM_HUES } from "@/shared/ui/timerMarks";

import { useNow } from "../hooks/useNow";
import { countdown } from "../lib/format";
import { byTime, type Filter, passes, type TimerNow, timersAt } from "../lib/model";
import { regionName, timerName } from "../lib/names";

import PlaqueRow from "./PlaqueRow";
import "./timers-plaque.css";

const HOTSPOT_PAD = 6;
const WORLD_ON_PLAQUE = 3;
const TABS: readonly { id: Filter; label: MessageKey }[] = [
  { id: "all", label: "timers.filter.all" },
  { id: "event", label: "timers.filter.event" },
  { id: "boss", label: "timers.filter.boss" },
];

/**
 * The timers plaque over the game (qt/timers_window.py), drawn as the steps plaque is: the warm
 * hairline round a dark backing, a head over the ice rule, the rows under it.
 *
 * The head holds the filter as tabs, the region, the pin and the fold; while pinned, the window
 * passes clicks through to the game but for that row of buttons, whose rectangle the page reports.
 * The rows are the timers on the plaque, soonest first and what runs leading, the world bosses no
 * more than three; the resets sit along the foot. Folded, only the nearest timer is left.
 */
export default function TimersPlaquePage() {
  const bridge = useTimersPlaqueApi();
  const data = useBackendState<TimersPlaqueData, TimersPlaqueData | null>((s) => s);
  const { t, setLanguage } = useI18n();
  const card = useRef<HTMLDivElement>(null);
  const sentHotspot = useRef("");
  const now = useNow(1000);

  const language = data?.language;
  useEffect(() => {
    if (language) setLanguage(language);
  }, [language, setLanguage]);

  useLayoutEffect(() => {
    const node = card.current;
    if (!node || !bridge) return undefined;
    const report = () => {
      const box = node.querySelector(".tp-live")?.getBoundingClientRect();
      const rect = box
        ? [
            Math.floor(box.left) - HOTSPOT_PAD,
            Math.floor(box.top) - HOTSPOT_PAD,
            Math.ceil(box.width) + 2 * HOTSPOT_PAD,
            Math.ceil(box.height) + 2 * HOTSPOT_PAD,
          ]
        : [0, 0, 0, 0];
      const key = rect.join(",");
      if (key !== sentHotspot.current) {
        sentHotspot.current = key;
        bridge.setHotspot(rect[0] ?? 0, rect[1] ?? 0, rect[2] ?? 0, rect[3] ?? 0);
      }
    };
    report();
    const observer = new ResizeObserver(report);
    observer.observe(node);
    return () => observer.disconnect();
  }, [bridge, data]);

  const startDrag = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      if (
        !bridge ||
        e.button !== 0 ||
        data?.pinned ||
        (e.target as Element).closest("button, .tp-grip")
      )
        return;
      e.preventDefault();
      bridge.dragStart();
      const stop = () => {
        bridge.dragEnd();
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    },
    [bridge, data?.pinned],
  );

  const timers = data?.timers ?? null;
  const all = useMemo(
    () => (timers && data ? timersAt(timers, now, data.worldLead) : []),
    [timers, data, now],
  );
  if (!data || !timers) return null;

  const filter = data.filter;
  let world = 0;
  const rows = all
    .filter((x) => x.shown && x.kind !== "reset" && passes(x, filter, "all"))
    .sort(byTime)
    .filter((x) => x.source !== "boss" || world++ < WORLD_ON_PLAQUE);
  const resets = all.filter((x) => x.kind === "reset");
  const region = timers.regions.find((r) => r.id === timers.region);
  const twelve = data.clock12h;
  const ringing = (x: TimerNow) =>
    data.ring !== null && data.ring.id === x.id && now < data.ring.start && !x.live;

  const style: CSSProperties = {
    "--tp-scale": data.scale,
    "--tp-alpha": data.opacity,
    "--tp-grip": `${data.grip}px`,
  };

  const groups =
    filter === "boss"
      ? (["abyss", "world"] as const).map((realm) => ({
          realm,
          rows: rows.filter((x) => x.realm === realm),
        }))
      : [{ realm: null, rows }];

  const first = rows[0];
  return (
    <div
      ref={card}
      className={`tp-card ${data.pinned ? "pinned" : "loose"}${data.collapsed ? " folded" : ""}`}
      style={style}
      onPointerDown={startDrag}
    >
      <div className="tp-head">
        {data.collapsed ? (
          first ? (
            <span className="tp-mini">
              <span className="tp-mini-name">{timerName(first, t)}</span>
              <span className="tp-mini-left">
                {first.target !== null ? countdown(first.target - now, t) : "—"}
              </span>
            </span>
          ) : (
            <span className="tp-mini" />
          )
        ) : null}
        <div className="tp-live">
          {data.collapsed ? null : (
            <div role="tablist" aria-label={t("timers.filter.label")} className="tp-tabs">
              {TABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={id === filter}
                  className={id === filter ? "tp-tab on" : "tp-tab"}
                  onClick={() => bridge?.action(`filter:${id}`)}
                >
                  {t(label)}
                </button>
              ))}
            </div>
          )}
          {data.collapsed ? null : (
            <span className="tp-region" title={region ? regionName(region, t) : ""}>
              {(region?.id ?? "").replace("global-", "").toUpperCase()}
            </span>
          )}
          <IconButton
            className={`tp-btn${data.pinned ? " on" : ""}`}
            label={data.pinned ? t("steps.unpin") : t("steps.pin")}
            icon={<Icon name={data.pinned ? "pinOn" : "pin"} />}
            onClick={() => bridge?.action("pin")}
          />
          <IconButton
            className="tp-btn"
            label={data.collapsed ? t("timers.plaque.unfold") : t("timers.plaque.fold")}
            icon={<Icon name={data.collapsed ? "chevronDown" : "up"} />}
            onClick={() => bridge?.action("collapse")}
          />
        </div>
        {data.pinned ? null : (
          <IconButton
            className="tp-btn tp-close"
            label={t("timers.plaque.hide")}
            icon={<Icon name="closeGlint" />}
            onClick={() => bridge?.action("close")}
          />
        )}
      </div>

      {data.collapsed ? null : (
        <>
          <div className="tp-rule" />
          <ul className="tp-list">
            {groups.map((g) => [
              g.realm && g.rows.length ? (
                <li
                  key={`kick-${g.realm}`}
                  className="tp-kick"
                  style={{ color: REALM_HUES[g.realm] }}
                >
                  {t(g.realm === "abyss" ? "timers.filter.abyss" : "timers.filter.world")}
                </li>
              ) : null,
              ...g.rows.map((x) => (
                <PlaqueRow
                  key={`${x.source}:${x.id}`}
                  timer={x}
                  now={now}
                  twelve={twelve}
                  ringing={ringing(x)}
                />
              )),
            ])}
          </ul>
          {resets.length ? (
            <div className="tp-foot">
              {resets.map((r) => (
                <span key={r.id}>
                  {timerName(r, t)} <b>{r.next !== null ? countdown(r.next - now, t) : "—"}</b>
                </span>
              ))}
            </div>
          ) : null}
        </>
      )}

      {data.pinned ? null : (
        <>
          <div className="tp-grip tp-grip-r" />
          <div className="tp-grip tp-grip-b" />
          <div className="tp-grip tp-grip-rb" />
        </>
      )}
    </div>
  );
}
