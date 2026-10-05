import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, Settings } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { available, languageName, useI18n } from "@/shared/i18n";
import Card from "@/shared/ui/Card";
import Segmented from "@/shared/ui/Segmented";

import UpdatesBlock from "./components/UpdatesBlock";

/**
 * The app's own settings, behind the gear beside the tool switch: the language and the updates.
 * Neither belongs to the map or to the timers, and both tools share them.
 */
export default function AppSettings() {
  const api = useApi();
  const { t } = useI18n();
  const changeSetting = useSettingsPatch();
  const state = useBackendState<AppState, AppState | null>((s) => s);
  if (!state || !api) return null;

  return (
    <div className="pn-section">
      <Card title={t("panel.settings.general")}>
        {/* The options come from the catalogues that shipped, so a new locales/<code>.json shows
            up by itself -- but Settings.language in core/settings.py still lists its choices,
            and that list has to grow with it. */}
        <Segmented
          label={t("panel.settings.language")}
          value={state.settings.language}
          options={[
            { value: "auto", label: t("panel.settings.languageAuto") },
            ...available.map((code) => ({
              value: code as Settings["language"],
              label: languageName(code),
            })),
          ]}
          tip={t("panel.settings.languageTip")}
          onChange={(v) => changeSetting("language", v)}
        />
      </Card>
      <UpdatesBlock
        settings={state.settings}
        update={state.update}
        version={state.version}
        isPortable={Boolean(state.isPortable)}
        onChange={changeSetting}
        onCheck={() => api.checkForUpdates()}
        onUnskip={() => api.skipUpdate("")}
      />
    </div>
  );
}
