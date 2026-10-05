import { type CSSProperties, memo } from "react";

import { useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import TimerMark from "@/shared/ui/TimerMark";
import { timerHue } from "@/shared/ui/timerMarks";

import { clock, countdown, day } from "../lib/format";
import { far, soon, type TimerNow } from "../lib/model";
import { timerName } from "../lib/names";

export interface PlaqueRowProps {
  timer: TimerNow;
  now: number;
  twelve: boolean;
  /** The reminder for it just sounded: marked until it starts. */
  ringing: boolean;
}

/**
 * One timer on the plaque. Running, it wears its hue with a line of how far along it is; within
 * its reminder window the countdown turns ice blue beside a bell, so the state never rests on the
 * colour alone; more than an hour off, it reads more quietly.
 */
function PlaqueRow({ timer, now, twelve, ringing }: PlaqueRowProps) {
  const { t, locale } = useI18n();
  const hue: CSSProperties = { "--tp-hue": timerHue(timer.icon) };
  const due = soon(timer, now);

  let sub = "";
  if (timer.live) {
    const state =
      timer.source === "boss"
        ? t("timers.status.up")
        : timer.live.entryCloses
          ? t("timers.status.entryOpen")
          : t("timers.status.running");
    sub =
      timer.source === "boss"
        ? state
        : `${state} · ${t("timers.status.until", {
            time: clock(timer.live.entryCloses ?? timer.live.end, locale, twelve),
          })}`;
  } else if (timer.next !== null) {
    sub = `${timer.estimated ? "~" : ""}${clock(timer.next, locale, twelve)} ${day(timer.next, now, locale, t)}`;
  }

  const classes = ["tp-row"];
  if (timer.live) classes.push("live");
  if (due) classes.push("soon");
  if (far(timer, now)) classes.push("far");
  if (ringing) classes.push("ring");
  return (
    <li className={classes.join(" ")} style={hue}>
      <TimerMark icon={timer.icon} size="sm" className="tp-mark" />
      <span className="tp-text">
        <span className="tp-name">{timerName(timer, t)}</span>
        <span className="tp-sub">{sub}</span>
      </span>
      <span className="tp-left">
        {due ? <Icon name="bell" className="tp-bell" /> : null}
        {timer.target !== null ? countdown(timer.target - now, t) : "—"}
      </span>
      {timer.live ? (
        <i
          className="tp-prog"
          style={{ "--tp-p": (now - timer.live.start) / (timer.live.end - timer.live.start) }}
          aria-hidden="true"
        />
      ) : null}
    </li>
  );
}

export default memo(PlaqueRow);
