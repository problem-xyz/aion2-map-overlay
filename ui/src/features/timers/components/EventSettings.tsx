import type { TimerSignal } from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";
import Switch from "@/shared/ui/Switch";
import TimerMark from "@/shared/ui/TimerMark";

/** The reminder leads the timers offer, in minutes; 0 is none (TIMER_LEADS in core/settings.py). */
export const LEADS = [0, 2, 5, 10, 15] as const;

export interface EventSettingsProps {
  icon: string;
  name: string;
  shown: boolean;
  lead: number;
  signal: TimerSignal;
  onShown: (shown: boolean) => void;
  onLead: (lead: number) => void;
  onSignal: (signal: TimerSignal) => void;
  onPreview: () => void;
}

/**
 * One event's choices in two lines: its name with the switch that puts it on the plaque, then how
 * long ahead it is announced and with what. The column heads are said once, over the group.
 */
export default function EventSettings({
  icon,
  name,
  shown,
  lead,
  signal,
  onShown,
  onLead,
  onSignal,
  onPreview,
}: EventSettingsProps) {
  const { t } = useI18n();
  return (
    <li className={`tm-set${shown ? "" : " off"}`}>
      <div className="tm-set-top">
        <TimerMark icon={icon} />
        <span className="tm-set-name">{name}</span>
        <Switch
          checked={shown}
          onChange={onShown}
          title={t("timers.settings.shownLabel", { name })}
        />
      </div>
      <div className="tm-set-controls">
        <Segmented
          label={t("timers.settings.leadLabel", { name })}
          labelHidden
          value={lead}
          options={LEADS.map((m) => ({
            value: m,
            label: m === 0 ? t("timers.settings.leadNone") : String(m),
          }))}
          onChange={onLead}
        />
        <Segmented
          label={t("timers.settings.signalLabel", { name })}
          labelHidden
          value={signal}
          options={[
            { value: "voice", label: t("timers.settings.voice") },
            { value: "chime", label: t("timers.settings.chime") },
          ]}
          onChange={onSignal}
        />
        <IconButton
          className="btn-small ghost tm-set-play"
          label={t("timers.settings.preview", { name })}
          icon={<Icon name="play" />}
          onClick={onPreview}
        />
      </div>
    </li>
  );
}
