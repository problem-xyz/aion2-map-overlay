import type { CSSProperties } from "react";

import { useI18n } from "@/shared/i18n";
import TimerMark from "@/shared/ui/TimerMark";
import { timerHue } from "@/shared/ui/timerMarks";

import { clock, countdown, day } from "../lib/format";
import type { TimerNow } from "../lib/model";
import { timerName } from "../lib/names";

export interface TimersHeroProps {
  /** What is running, else what starts soonest, of the timers on the plaque. */
  lead: TimerNow | null;
  resets: TimerNow[];
  now: number;
  twelve: boolean;
}

/**
 * The timers' leading card, as the map's shows the route: the one thing to know first -- what is
 * on now, or next -- large, in its own hue, and the two resets along its foot.
 */
export default function TimersHero({ lead, resets, now, twelve }: TimersHeroProps) {
  const { t, locale } = useI18n();
  const hue: CSSProperties | undefined = lead ? { "--tm-hue": timerHue(lead.icon) } : undefined;

  let meta = "";
  if (lead?.live) {
    const until = clock(lead.live.entryCloses ?? lead.live.end, locale, twelve);
    meta = t("timers.status.until", { time: until });
  } else if (lead?.next != null) {
    const start = clock(lead.next, locale, twelve);
    const end =
      lead.nextEnd && lead.nextEnd > lead.next ? `–${clock(lead.nextEnd, locale, twelve)}` : "";
    meta = `${day(lead.next, now, locale, t)} ${start}${end}`;
  }
  const status = lead?.live
    ? lead.live.entryCloses
      ? t("timers.status.entryOpen")
      : lead.source === "boss"
        ? t("timers.status.up")
        : t("timers.status.running")
    : "";

  return (
    <section className="ui-frame tm-hero" style={hue} aria-label={t("timers.label")}>
      {lead ? (
        <div className={`tm-hero-main${lead.live ? " live" : ""}`}>
          <TimerMark icon={lead.icon} size="lg" />
          <div className="tm-hero-body">
            <div className="tm-hero-name">{timerName(lead, t)}</div>
            <div className="tm-hero-meta">
              {status ? <b>{status}</b> : null}
              {status ? " · " : null}
              {meta}
            </div>
          </div>
          <div className="tm-hero-left">
            {lead.target !== null ? countdown(lead.target - now, t) : "—"}
          </div>
          {lead.live ? (
            <i
              className="tm-hero-prog"
              style={{ "--tm-p": (now - lead.live.start) / (lead.live.end - lead.live.start) }}
              aria-hidden="true"
            />
          ) : null}
        </div>
      ) : null}
      {resets.length ? (
        <div className="tm-hero-resets">
          {resets.map((r) => (
            <span key={r.id}>
              <TimerMark icon={r.icon} size="sm" className="tm-hero-reset-mark" />
              {timerName(r, t)} <b>{r.next !== null ? countdown(r.next - now, t) : "—"}</b>
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}
