import { useState } from "react";

import type { UpdateState } from "@/shared/backend/contract";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { useI18n } from "@/shared/i18n";

export interface UpdateBannerProps {
  update: UpdateState | undefined;
  /** getState's repoUrl; without it (an older backend) there is no release notes link. */
  repoUrl: string | undefined;
  /** An open route editor loses unsaved changes on a restart, so Restart now asks first. */
  editorOpen: boolean;
  onDownload: () => void;
  onRestart: () => void;
  onSkip: (version: string) => void;
  onOpenUrl: (url: string) => void;
}

/**
 * A new version, from finding it to installing it.
 *
 * Shown for `available`, `downloading` and `ready`, unless the user skipped that version or put
 * it off with "Later" in this session. "Later" only hides the banner: a downloaded update is
 * still installed when the app closes, which is the point of downloading it. Failures are left
 * to the notice and to the Updates block, where "Check now" is.
 */
export default function UpdateBanner({
  update,
  repoUrl,
  editorOpen,
  onDownload,
  onRestart,
  onSkip,
  onOpenUrl,
}: UpdateBannerProps) {
  const { t, format } = useI18n();
  const confirm = useConfirm();
  const [later, setLater] = useState<string | null>(null);

  if (!update || update.skipped || !update.version) return null;
  const { phase, version } = update;
  if (phase !== "available" && phase !== "downloading" && phase !== "ready") return null;
  if (later === version && phase !== "downloading") return null;

  const notesUrl = repoUrl ? `${repoUrl}/releases/tag/v${version}` : null;
  const progress = Math.max(0, Math.min(100, update.progress ?? 0));

  return (
    <section className="pn-update" role="status" aria-live="polite">
      <p className="pn-update-text">
        {phase === "available"
          ? t("panel.update.available", { version })
          : phase === "downloading"
            ? t("panel.update.downloading", { version })
            : t("panel.update.ready", { version })}
      </p>

      {phase === "downloading" ? (
        <div className="pn-update-progress">
          <progress max={100} value={progress} aria-label={t("panel.update.progressLabel")} />
          <span className="muted">{format.percent(progress / 100)}</span>
        </div>
      ) : (
        <div className="pn-update-actions">
          {phase === "ready" ? (
            <button
              type="button"
              className="btn-small pn-update-primary"
              onClick={() => {
                if (!editorOpen) {
                  onRestart();
                  return;
                }
                void confirm(t("panel.update.confirmRestartEditor"), {
                  confirmLabel: t("panel.update.restartNow"),
                }).then((ok) => {
                  if (ok) onRestart();
                });
              }}
            >
              {t("panel.update.restartNow")}
            </button>
          ) : (
            <button type="button" className="btn-small pn-update-primary" onClick={onDownload}>
              {t("panel.update.download")}
            </button>
          )}
          <button type="button" className="btn-small ghost" onClick={() => setLater(version)}>
            {t("panel.update.later")}
          </button>
          <button type="button" className="btn-small ghost" onClick={() => onSkip(version)}>
            {t("panel.update.skip")}
          </button>
          {notesUrl ? (
            <button type="button" className="pn-update-link" onClick={() => onOpenUrl(notesUrl)}>
              {t("panel.update.releaseNotes")}
            </button>
          ) : null}
        </div>
      )}
    </section>
  );
}
