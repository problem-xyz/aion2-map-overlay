import type { CSSProperties } from "react";

import type { ProgressState } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import MarkIcon from "@/shared/ui/MarkIcon";
import type { MarkIconName } from "@/shared/ui/markIcons";

import Card from "./Card";

// The number's colour and the bar's share travel in CSS variables, which CSSProperties does not
// know about
interface NumColorStyle extends CSSProperties {
  "--num-color": string;
}
interface ShareStyle extends CSSProperties {
  "--share": string;
}

function numStyle(color: string): NumColorStyle {
  return { "--num-color": color };
}

export interface ProgressBlockProps {
  progress: ProgressState;
  /** Each point's icon, as the editor's list shows it, in the order of progress.markers. */
  icons?: readonly (MarkIconName | null)[];
  onSet: (done: number) => void;
  onReset: () => void;
}

/** How far along the route is, and every point with the box that marks it passed. It always
 * counts: there used to be a switch to turn progress off, and nobody could say what for. */
export default function ProgressBlock({
  progress,
  icons = [],
  onSet,
  onReset,
}: ProgressBlockProps) {
  const t = useT();
  const { done, total, markers } = progress;
  const finished = total > 0 && done >= total;
  const share: ShareStyle = { "--share": String(total > 0 ? done / total : 0) };

  return (
    <Card title={t("panel.progress.title")}>
      {total === 0 ? (
        <p className="muted pn-card-text">{t("panel.progress.noRoute")}</p>
      ) : (
        <>
          <div className="pn-meter">
            <div className="pn-meter-line">
              <span className={finished ? "pn-meter-done" : ""}>
                {finished
                  ? t("panel.progress.finished")
                  : t("panel.progress.done", {
                      done,
                      total: t("common.points", { count: total }),
                    })}
              </span>
              <button type="button" className="btn-small" onClick={onReset} disabled={done === 0}>
                {t("panel.progress.reset")}
              </button>
            </div>
            <div className="pn-meter-bar" style={share} aria-hidden="true" />
          </div>

          {/* The points as the editor lists them -- number, the icon of what the point is, label
              -- each with the box that marks it passed */}
          <ul className="progress-list">
            {markers.map((m, i) => {
              const icon = icons[i];
              return (
                <li key={m.n} className={m.n <= done ? "passed" : ""}>
                  <label className="progress-row">
                    <input
                      type="checkbox"
                      checked={m.n <= done}
                      onChange={(e) => onSet(e.target.checked ? m.n : m.n - 1)}
                    />
                    <span className="progress-num ui-badge-num" style={numStyle(m.color)}>
                      {m.n}
                    </span>
                    {icon ? <MarkIcon name={icon} className="progress-icon" /> : null}
                    <span className={m.text ? "progress-text" : "progress-text ph"}>
                      {m.text || t("panel.progress.noLabel")}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Card>
  );
}
