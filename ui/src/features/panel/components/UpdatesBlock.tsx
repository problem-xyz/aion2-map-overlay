import type { Settings, UpdateState } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import Switch from "@/shared/ui/Switch";

import Card from "./Card";
import type { SettingsChange } from "./SettingsBlock";

export interface UpdatesBlockProps {
  settings: Settings;
  update: UpdateState | undefined;
  /** The running version, as the footer shows it. */
  version: string;
  isPortable: boolean;
  onChange: SettingsChange;
  onCheck: () => void;
  /** Forget a skipped version, so it is offered again. */
  onUnskip: () => void;
}

/**
 * How the app keeps itself up to date, and what it last found.
 *
 * A source checkout or a copied build is not a Velopack install, and the updater says so with
 * `disabled`: the switches still show what is set, but nothing here can act on it.
 */
export default function UpdatesBlock({
  settings,
  update,
  version,
  isPortable,
  onChange,
  onCheck,
  onUnskip,
}: UpdatesBlockProps) {
  const t = useT();
  const phase = update?.phase ?? "disabled";
  const enabled = phase !== "disabled";
  const busy = phase === "checking" || phase === "downloading";
  const skipped = settings.updates_skipped_version;

  const status =
    phase === "disabled"
      ? t("panel.updates.unavailable")
      : phase === "checking"
        ? t("panel.updates.checking")
        : phase === "none"
          ? t("panel.updates.latest")
          : phase === "failed"
            ? t("panel.updates.failed", { reason: update?.reason ?? "" })
            : null;

  return (
    <Card
      title={t("panel.updates.title")}
      aside={
        <button type="button" className="btn-small" disabled={!enabled || busy} onClick={onCheck}>
          {t("panel.updates.checkNow")}
        </button>
      }
    >
      <div className="pn-card-text">
        <p className="pn-updates-version">
          {t("panel.updates.current", { version })}
          {isPortable ? <span className="muted"> · {t("panel.updates.portable")}</span> : null}
        </p>
        {status ? <p className="ui-hint">{status}</p> : null}
      </div>

      <Switch
        checked={settings.updates_auto_check}
        disabled={!enabled}
        onChange={(on) => onChange("updates_auto_check", on)}
        label={t("panel.updates.autoCheck")}
      />
      <Switch
        checked={settings.updates_auto_download}
        disabled={!enabled}
        onChange={(on) => onChange("updates_auto_download", on)}
        label={t("panel.updates.autoDownload")}
      />

      {skipped ? (
        <div className="pn-updates-skipped">
          <span className="muted">{t("panel.updates.skipped", { version: skipped })}</span>
          <button type="button" className="btn-small ghost" onClick={onUnskip}>
            {t("panel.updates.unskip")}
          </button>
        </div>
      ) : null}
    </Card>
  );
}
