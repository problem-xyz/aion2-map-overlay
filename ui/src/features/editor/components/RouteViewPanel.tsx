import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, EditorRouteView } from "@/shared/backend/contract";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { useI18n } from "@/shared/i18n";
import Segmented from "@/shared/ui/Segmented";
import SettingSlider from "@/shared/ui/SettingSlider";

import { useEditorState } from "../EditorContext";

const selectSchema = (s: AppState | null) => s?.settingsSchema;

/**
 * How the route is drawn in the editor: the lines' opacity, and whether a selected point fades
 * the route away from itself. The overlay's own card in the panel has one choice more, "steps",
 * that leaves out the rest of the route; the editor always draws every point, since every point
 * is what is being edited.
 */
export default function RouteViewPanel() {
  const { t, format } = useI18n();
  const { view } = useEditorState();
  const schema = useBackendState(selectSchema);
  const change = useSettingsPatch();

  return (
    <div className="ed-view">
      <SettingSlider
        name="editor_opacity"
        schema={schema}
        label={t("editor.view.opacity")}
        value={view.opacity}
        format={(v) => format.percent(v)}
        tip={t("editor.view.opacityTip")}
        onChange={(v) => change("editor_opacity", v)}
      />
      <Segmented<EditorRouteView>
        label={t("editor.view.show")}
        value={view.mode}
        options={[
          { value: "dim", label: t("editor.view.dim") },
          { value: "all", label: t("editor.view.all") },
        ]}
        tip={t("editor.view.showTip")}
        onChange={(v) => change("editor_route_view", v)}
      />
      {view.mode === "dim" ? (
        <SettingSlider
          name="editor_route_ahead"
          schema={schema}
          label={t("editor.view.ahead")}
          value={view.ahead}
          format={(v) => format.number(v)}
          tip={t("editor.view.aheadTip")}
          onChange={(v) => change("editor_route_ahead", v)}
        />
      ) : null}
    </div>
  );
}
