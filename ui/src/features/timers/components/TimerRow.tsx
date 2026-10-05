import { type CSSProperties, memo } from "react";

import { useI18n } from "@/shared/i18n";
import TimerMark from "@/shared/ui/TimerMark";
import { timerHue } from "@/shared/ui/timerMarks";

import { clock, countdown, day, duration, frequency, span } from "../lib/format";
import { far, type TimerNow } from "../lib/model";
import { timerName } from "../lib/names";

export interface TimerRowProps {
  timer: TimerNow;
  now: number;
  twelve: boolean;
  /** The world boss's cycle needs fixing: the game showed more time left than it. */
  wrongCycle?: boolean;
}

/**
 * One timer in the schedule: its mark, its name and how often it comes round, the countdown, and
 * when -- or, while it runs, that it does and until when. A running timer wears its own hue.
 */
function TimerRow({ timer, now, twelve, wrongCycle = false }: TimerRowProps) {
  const { t, locale } = useI18n();
  const hue: CSSProperties = { "--tm-hue": timerHue(timer.icon) };
  const name = timerName(timer, t);

  let sub = "";
  if (timer.event) {
    sub = [frequency(timer.event, locale, t), span(timer.event, t)].filter(Boolean).join(" · ");
  } else if (timer.boss) {
    const cycle = duration(timer.boss.respawnS * 1000, t);
    sub = [timer.boss.area, t("timers.world.respawn", { cycle })].filter(Boolean).join(" · ");
  }

  let when = "";
  let status = "";
  if (timer.live) {
    status =
      timer.source === "boss"
        ? t("timers.status.up")
        : timer.live.entryCloses
          ? t("timers.status.entryOpen")
          : t("timers.status.running");
    if (timer.source === "event") {
      when = t("timers.status.until", {
        time: clock(timer.live.entryCloses ?? timer.live.end, locale, twelve),
      });
    }
  } else if (timer.next !== null) {
    const at = clock(timer.next, locale, twelve);
    when = `${timer.estimated ? "~" : ""}${day(timer.next, now, locale, t)} ${at}`;
  }

  const left = timer.target !== null ? countdown(timer.target - now, t) : "—";
  const quiet = far(timer, now);
  return (
    <li className={`tm-row${timer.live ? " live" : ""}`} style={hue}>
      <TimerMark icon={timer.icon} />
      <span className="tm-row-text">
        <span className="tm-row-name">{name}</span>
        {sub ? <span className="tm-row-sub">{sub}</span> : null}
      </span>
      <span className="tm-row-when">
        <span className={`tm-row-left${quiet ? " far" : ""}`}>{left}</span>
        <span className="tm-row-at">
          {status ? <b>{status}</b> : null}
          {status && when ? " · " : null}
          {when}
          {timer.estimated && !timer.live ? (
            <span className="ui-sr-only"> ({t("timers.status.estimated")})</span>
          ) : null}
        </span>
        {wrongCycle ? (
          <span className="tm-row-warn" title={t("timers.world.wrongCycle")}>
            !<span className="ui-sr-only">{t("timers.world.wrongCycle")}</span>
          </span>
        ) : null}
      </span>
      {timer.live ? (
        <i
          className="tm-row-prog"
          style={{ "--tm-p": (now - timer.live.start) / (timer.live.end - timer.live.start) }}
          aria-hidden="true"
        />
      ) : null}
    </li>
  );
}

export default memo(TimerRow);
