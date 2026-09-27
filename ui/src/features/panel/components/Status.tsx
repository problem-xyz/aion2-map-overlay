import { useEffect, useState } from "react";

import { useBackendSignal } from "@/shared/backend/BackendProvider";
import type { Stats } from "@/shared/backend/contract";
import { useI18n, useT, type MessageKey } from "@/shared/i18n";

// A plain function cannot call a hook, so it names the message and the header translates it.
interface Mode {
  key: "idle" | "search" | "found";
  message: MessageKey;
}

function mode(running: boolean, stats: Stats | null): Mode {
  if (!running) return { key: "idle", message: "panel.status.idle" };
  if (!stats || !stats.found) return { key: "search", message: "panel.status.searching" };
  // the map is on screen, but the last detect did not confirm the anchor: we hold on to the
  // frame-to-frame motion instead
  if (!stats.anchored) return { key: "search", message: "panel.status.flow" };
  return { key: "found", message: "panel.status.found" };
}

interface NumProps {
  value: number | null | undefined;
  unit?: string;
  label: string;
}

function Num({ value, unit = "", label }: NumProps) {
  const { format } = useI18n();
  const shown = value === null || value === undefined ? "—" : format.number(value);
  return (
    <div className="num">
      <div className="num-value">
        {shown}
        {value !== null && value !== undefined && unit ? <small>{unit}</small> : null}
      </div>
      <div className="num-label">{label}</div>
    </div>
  );
}

/**
 * Subscribes to statsChanged itself rather than taking stats as a prop, so a tick four times
 * a second re-renders this strip and nothing else in the panel.
 */
export interface StatusProps {
  running: boolean;
}

export default function Status({ running }: StatusProps) {
  const t = useT();
  const [stats, setStats] = useState<Stats | null>(null);
  useBackendSignal<Stats | null>("statsChanged", setStats, { parse: true });
  useEffect(() => {
    if (!running) setStats(null);
  }, [running]);

  const m = mode(running, stats);
  const s: Partial<Stats> = stats || {};
  return (
    <header className={`status status-${m.key}`}>
      <div className="status-line">
        <span className="dot" />
        {/* The live region is this span and nothing wider. The numbers below tick four times a
            second, and inside a live region every tick would be read out over whatever the user
            was listening to; the mode changes a handful of times per session. */}
        <span className="status-text" aria-live="polite">
          {t(m.message)}
        </span>
      </div>
      <div className="nums">
        <Num value={s.fps} label={t("panel.stats.fps")} />
        <Num value={s.processMs} unit={t("panel.stats.ms")} label={t("panel.stats.frame")} />
        <Num value={s.detectMs} unit={t("panel.stats.ms")} label={t("panel.stats.detect")} />
        <Num value={s.reprojError} unit="px" label={t("panel.stats.error")} />
      </div>
    </header>
  );
}
