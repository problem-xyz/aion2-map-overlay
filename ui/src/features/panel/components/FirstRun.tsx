import { useT } from "@/shared/i18n";

export interface FirstRunProps {
  onDraw: () => void;
}

/**
 * What a fresh install shows where the active route will be: the two steps to the route on the
 * game map. There used to be three, and the middle one sent the user off to select the map
 * area; Start does that itself now, the first time, so a route is all there is to make.
 */
export default function FirstRun({ onDraw }: FirstRunProps) {
  const t = useT();
  return (
    <section className="ui-frame ui-orn pn-first-run" aria-labelledby="pn-first-run-title">
      <h2 id="pn-first-run-title" className="ui-title">
        {t("panel.firstRun.title")}
      </h2>
      <ol className="pn-first-run-steps">
        <li>
          <span className="pn-first-run-mark ui-badge-num" aria-hidden="true">
            1
          </span>
          <span className="pn-first-run-text">{t("panel.firstRun.route")}</span>
          <button type="button" className="btn-small" onClick={onDraw}>
            {t("panel.firstRun.routeAction")}
          </button>
        </li>
        <li>
          <span className="pn-first-run-mark ui-badge-num" aria-hidden="true">
            2
          </span>
          <span className="pn-first-run-text">{t("panel.firstRun.start")}</span>
        </li>
      </ol>
      <p className="ui-hint pn-first-run-hint">{t("panel.status.fullscreenHint")}</p>
    </section>
  );
}
