import { useI18n } from "@/shared/i18n";

/** The timers tool of the control panel. */
export default function TimersPage() {
  const { t } = useI18n();
  return <p className="muted">{t("app.tools.timers")}</p>;
}
