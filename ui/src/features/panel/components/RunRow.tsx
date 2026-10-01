import { useId, useLayoutEffect, useRef } from "react";

import { useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import Sheen from "@/shared/ui/Sheen";

export interface RunRowProps {
  running: boolean;
  /**
   * A route is chosen, or the cubes are on and a Start asks for the map. The map area is not
   * needed: a Start without one asks for it first.
   */
  canStart: boolean;
  /** The checklist over the game: state.steps.visible. */
  checklistVisible: boolean;
  overlayVisible: boolean;
  captureVisible: boolean;
  /**
   * getState's captureExclusion: false on a Windows too old to hide a window from capture.
   * Absent from a backend before api 4, which could always hide the overlay.
   */
  captureExclusion: boolean | undefined;
  onStart: () => void;
  onStop: () => void;
  onChecklistVisible: (visible: boolean) => void;
  onOverlayVisible: (visible: boolean) => void;
  onCaptureVisible: (visible: boolean) => void;
}

/**
 * Start or Stop, and beside it the toggles for what is drawn over the game and who can see it --
 * the checklist, the arrows, the recordings -- in one row like the client's action bar: the main
 * button and its quick slots.
 */
export default function RunRow({
  running,
  canStart,
  checklistVisible,
  overlayVisible,
  captureVisible,
  captureExclusion,
  onStart,
  onStop,
  onChecklistVisible,
  onOverlayVisible,
  onCaptureVisible,
}: RunRowProps) {
  const { t, locale } = useI18n();
  const warningId = useId();
  const row = useRef<HTMLDivElement>(null);
  const canHide = captureExclusion !== false;

  // Three quick slots with their names leave Start too little room in a narrow panel, and in
  // Russian at the default width. Then the slots show their icons alone, the name staying their
  // tooltip and their accessible name. Measured with the names shown, every time, so the answer
  // never depends on the last one; the class is set here rather than through state, so a
  // measurement costs no second render.
  useLayoutEffect(() => {
    const node = row.current;
    const start = node?.firstElementChild;
    if (!node || !start) return undefined;
    const fit = () => {
      node.classList.remove("compact");
      node.classList.toggle("compact", start.scrollWidth > start.clientWidth);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(node);
    return () => observer.disconnect();
  }, [locale, running, canStart]);

  return (
    <>
      <div ref={row} className="pn-run">
        {running ? (
          <button className="btn btn-stop ui-with-icon" onClick={onStop}>
            <Icon name="stop" />
            {t("panel.run.stop")}
          </button>
        ) : (
          <button
            className="btn btn-start ui-with-icon"
            disabled={!canStart}
            onClick={onStart}
            title={canStart ? "" : t("panel.run.startDisabledTip")}
          >
            {canStart ? <Sheen tone="gold" /> : null}
            <Icon name="play" />
            {t("panel.run.start")}
          </button>
        )}
        {/* Checkboxes still, drawn as the client's quick slots: the state is the native one, so
            it is announced and tabbed to like any checkbox. The full sentence is the tooltip. */}
        <label className="pn-chip" title={t("panel.run.checklist")}>
          <input
            type="checkbox"
            checked={checklistVisible}
            onChange={(e) => onChecklistVisible(e.target.checked)}
            aria-label={t("panel.run.checklist")}
          />
          <Icon name="list" className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("panel.run.checklistShort")}
          </span>
        </label>
        <label className="pn-chip" title={t("panel.run.showArrows")}>
          <input
            type="checkbox"
            checked={overlayVisible}
            onChange={(e) => onOverlayVisible(e.target.checked)}
            aria-label={t("panel.run.showArrows")}
          />
          <Icon name={overlayVisible ? "eye" : "eyeOff"} className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("panel.run.arrowsShort")}
          </span>
        </label>
        {/* Where Windows cannot hide it, the overlay is visible whatever this says, so the box
            shows that and cannot be unticked -- and the tooltip, which tells the user to turn
            it on, gives way to the warning below. */}
        <label
          className="pn-chip"
          title={canHide ? t("panel.run.visibleInRecordingTip") : undefined}
        >
          <input
            type="checkbox"
            checked={captureVisible || !canHide}
            disabled={!canHide}
            aria-describedby={canHide ? undefined : warningId}
            aria-label={t("panel.run.visibleInRecording")}
            onChange={(e) => onCaptureVisible(e.target.checked)}
          />
          <Icon name="record" className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("panel.run.recordingShort")}
          </span>
        </label>
      </div>
      {canHide ? null : (
        <p id={warningId} className="pn-capture-warning">
          {t("panel.run.captureExclusionOff")}
        </p>
      )}
    </>
  );
}
