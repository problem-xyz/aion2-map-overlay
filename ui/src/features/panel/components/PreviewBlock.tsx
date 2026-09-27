import { useEffect, useState, type MouseEvent } from "react";

import { useBackendSignal } from "@/shared/backend/BackendProvider";
import { useT } from "@/shared/i18n";
import Switch from "@/shared/ui/Switch";

/**
 * Owns the preview frame. It arrives four times a second and is only shown here, so keeping
 * it in App would re-render the whole panel for a picture nobody else looks at.
 *
 * Two rows of the Map area card: the switch, and under it the picture while it is on.
 */
export interface PreviewBlockProps {
  enabled: boolean;
  running: boolean;
  showAnchor: boolean;
  onToggle: (enabled: boolean) => void;
  onAnchor?: (fx: number, fy: number) => void;
}

export default function PreviewBlock({
  enabled,
  running,
  showAnchor,
  onToggle,
  onAnchor,
}: PreviewBlockProps) {
  const t = useT();
  const [image, setImage] = useState<string | null>(null);
  useBackendSignal("previewChanged", (b64) => setImage(b64 || null));
  useEffect(() => {
    // a stale frame under a stopped engine reads as if it were live
    if (!running || !enabled) setImage(null);
  }, [running, enabled]);

  const pick = (e: MouseEvent<HTMLImageElement>) => {
    if (!onAnchor) return;
    const box = e.currentTarget.getBoundingClientRect();
    if (!box.width || !box.height) return;
    onAnchor((e.clientX - box.left) / box.width, (e.clientY - box.top) / box.height);
  };

  return (
    <>
      <Switch
        checked={enabled}
        onChange={onToggle}
        label={t("panel.preview.title")}
        hint={t("panel.preview.off")}
      />
      {enabled ? (
        image ? (
          <div className="pn-preview">
            {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- TODO: accessibility pass */}
            <img
              className={`preview ${showAnchor ? "pickable" : ""}`}
              src={`data:image/jpeg;base64,${image}`}
              alt={t("panel.preview.alt")}
              onClick={showAnchor ? pick : undefined}
            />
            {showAnchor ? <p className="ui-hint">{t("panel.preview.anchorHint")}</p> : null}
          </div>
        ) : (
          <p className="muted pn-card-text">
            {running ? t("panel.preview.waiting") : t("panel.preview.stopped")}
          </p>
        )
      ) : null}
    </>
  );
}
