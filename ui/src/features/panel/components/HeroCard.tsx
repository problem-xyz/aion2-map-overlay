import type { ReactNode } from "react";

import type { ProgressState, Region, RouteInfo } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import MarkIcon from "@/shared/ui/MarkIcon";
import type { MarkIconName } from "@/shared/ui/markIcons";

export interface HeroCardProps {
  route: RouteInfo | undefined;
  progress: ProgressState;
  region: Region | null;
  /** The icon of the point that comes next: its quest star, or the object it sits on. */
  nextIcon?: MarkIconName | null;
  /** The strip along the card's foot: what the engine is doing, and its numbers. */
  children?: ReactNode;
}

const RING_R = 36;
const RING_C = 2 * Math.PI * RING_R;

/**
 * The active route, framed like the client's character card: how far along it is, what it is
 * called, and the point that comes next. The panel opens on it, so the one thing a player
 * checks between two fights is the first thing on screen. The engine's status runs along its
 * foot, where it used to stand alone on a line of its own under the buttons.
 */
export default function HeroCard({
  route,
  progress,
  region,
  nextIcon = null,
  children,
}: HeroCardProps) {
  const t = useT();
  const total = route ? progress.total || route.markers : 0;
  const done = Math.min(progress.done, total);
  const share = total > 0 ? done / total : 0;
  const next = progress.markers[done];

  return (
    <section className="ui-frame ui-orn pn-hero" aria-label={t("panel.hero.kicker")}>
      <div className="pn-hero-main">
        <div className="pn-ring" aria-hidden="true">
          <svg viewBox="0 0 84 84">
            <defs>
              <linearGradient id="pn-ring-gold" x1="0" x2="1">
                <stop offset="0" />
                <stop offset="1" />
              </linearGradient>
            </defs>
            <circle className="pn-ring-track" cx="42" cy="42" r={RING_R} />
            {share > 0 ? (
              <circle
                className="pn-ring-fill"
                cx="42"
                cy="42"
                r={RING_R}
                strokeDasharray={RING_C}
                strokeDashoffset={RING_C * (1 - share)}
              />
            ) : null}
          </svg>
          <b>{done}</b>
          <small>{t("panel.hero.of", { total })}</small>
        </div>

        <div className="pn-hero-body">
          <div className="pn-hero-kicker">{t("panel.hero.kicker")}</div>
          {route ? (
            <>
              <h1 className="pn-hero-name">{route.label}</h1>
              <p className="pn-hero-meta">
                {route.mapLabel || route.map} · {t("common.points", { count: total })} ·{" "}
                {region
                  ? t("panel.hero.area", { width: region.width, height: region.height })
                  : t("panel.hero.noArea")}
              </p>
              <p className="pn-hero-next">
                {next ? (
                  <>
                    <span className="pn-sr-only">{t("panel.hero.next")}: </span>
                    <span className="pn-hero-num" style={{ "--num-color": next.color }}>
                      {next.n}
                    </span>
                    {nextIcon ? <MarkIcon name={nextIcon} className="pn-hero-icon" /> : null}
                    <span className="pn-hero-next-text">
                      {next.text || t("panel.hero.unnamed", { n: next.n })}
                    </span>
                  </>
                ) : (
                  <span className="pn-hero-next-text">{t("panel.hero.done")}</span>
                )}
              </p>
            </>
          ) : (
            <>
              <h1 className="pn-hero-name muted">{t("panel.hero.none")}</h1>
              <p className="pn-hero-meta">{t("panel.hero.noneHint")}</p>
            </>
          )}
        </div>
      </div>
      {children}
    </section>
  );
}
