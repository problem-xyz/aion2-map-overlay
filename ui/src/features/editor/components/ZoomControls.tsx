import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";

import { useEditorActions } from "../EditorContext";

/** Zoom by half a level, and frame the whole route: the wheel alone never gets back to it. */
export default function ZoomControls() {
  const t = useT();
  const actions = useEditorActions();
  return (
    <div className="ui-frame ed-zoom" role="group" aria-label={t("editor.zoom.label")}>
      <IconButton
        className="ed-icon-btn"
        icon={<Icon name="plus" />}
        label={t("editor.zoom.in")}
        onClick={actions.zoomIn}
      />
      <IconButton
        className="ed-icon-btn"
        icon={<Icon name="minus" />}
        label={t("editor.zoom.out")}
        onClick={actions.zoomOut}
      />
      <IconButton
        className="ed-icon-btn"
        icon={<Icon name="fit" />}
        label={t("editor.zoom.fit")}
        onClick={actions.fitRoute}
      />
    </div>
  );
}
