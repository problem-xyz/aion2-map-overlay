import type { CSSProperties } from "react";

import type { MarkerIcon } from "@/shared/backend/contract";
import { type MessageKey, useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import MarkIcon from "@/shared/ui/MarkIcon";
import { questIcon } from "@/shared/ui/markIcons";

import { useEditorActions, useEditorState } from "../EditorContext";
import { objectLabel } from "../lib/objectsIndex";
import { MARKER_COLORS } from "../lib/palette";

import { INSPECTOR_TEXT_ID } from "./PointsPanel";

function swatchStyle(color: string): CSSProperties {
  return { "--swatch": color };
}

/**
 * Everything about the selected point, in the drawer that slides out on the right when a point
 * is picked: its label with the room of a paragraph and the object it sits on under it, its
 * colour, where it is, and the moves and removal. Escape, or the cross, puts it away again.
 */
/** The icons a point can be given beside its number: none, a main quest, a side quest. */
const ICON_CHOICES: readonly { value: MarkerIcon | null; labelKey: MessageKey }[] = [
  { value: null, labelKey: "editor.icons.none" },
  { value: "main", labelKey: "editor.icons.main" },
  { value: "side", labelKey: "editor.icons.side" },
];

export default function Inspector() {
  const { markers, selectedId, style, objects } = useEditorState();
  const actions = useEditorActions();
  const { t, format } = useI18n();

  const index = markers.findIndex((m) => m.id === selectedId);
  const marker = index < 0 ? undefined : markers[index];
  if (!marker) return null;

  const total = markers.length;
  const color = marker.color || style.color;
  const onObject = objects ? objects.nearest(marker.x, marker.y, 1, null) : null;
  const onIcon = onObject ? (objects?.byId.get(onObject.cat)?.icon ?? null) : null;

  return (
    <aside className="ui-frame ed-inspector" aria-labelledby="ed-inspector-title">
      <header className="ed-insp-head">
        <span className="ed-insp-num" style={{ "--step-color": color }} aria-hidden="true">
          {index + 1}
        </span>
        <div className="ed-insp-heading">
          <h2 id="ed-inspector-title">{t("editor.inspector.title", { n: index + 1, total })}</h2>
        </div>
        <IconButton
          className="ed-icon-btn"
          icon={<Icon name="close" />}
          label={t("editor.inspector.close")}
          title={`${t("editor.inspector.close")} · Esc`}
          onClick={() => actions.select(null)}
        />
      </header>
      <div className="ed-insp-rule" aria-hidden="true" />

      <div className="ed-insp-body">
        <label className="ed-insp-label" htmlFor={INSPECTOR_TEXT_ID}>
          {t("editor.inspector.textLabel")}
        </label>
        <textarea
          id={INSPECTOR_TEXT_ID}
          className="ed-insp-text"
          rows={3}
          value={marker.text}
          placeholder={t("editor.inspector.textPlaceholder")}
          onFocus={actions.beginEdit}
          onBlur={() => actions.endEdit()}
          onChange={(e) => actions.setText(marker.id, e.target.value)}
        />
        {/* right under the label: the object a point sits on is usually what the label says */}
        {onObject ? (
          <p className="ed-insp-object">
            {onIcon ? (
              <MarkIcon name={onIcon} className="ed-insp-object-icon" />
            ) : (
              <Icon name="target" />
            )}
            <span>
              {t("editor.inspector.onObject")}: <b>{objectLabel(onObject)}</b>
            </span>
          </p>
        ) : null}

        <div className="ed-insp-label" id="ed-insp-colour">
          {t("editor.inspector.color")}
          <span className="muted"> · {t("editor.inspector.colorHint")}</span>
        </div>
        <div className="ed-swatches" role="group" aria-labelledby="ed-insp-colour">
          <IconButton
            className="swatch none"
            label={t("editor.colors.asRoute")}
            icon={<Icon name="close" />}
            aria-pressed={marker.color === undefined}
            onClick={() => actions.setColor(marker.id, null)}
          />
          {MARKER_COLORS.map(({ value, nameKey }) => (
            <IconButton
              key={value}
              className="swatch"
              style={swatchStyle(value)}
              label={t(nameKey)}
              icon={null}
              aria-pressed={marker.color === value}
              onClick={() => actions.setColor(marker.id, value)}
            />
          ))}
        </div>

        <div className="ed-insp-label" id="ed-insp-icon">
          {t("editor.inspector.icon")}
        </div>
        <div className="ed-insp-icons" role="group" aria-labelledby="ed-insp-icon">
          {ICON_CHOICES.map(({ value, labelKey }) => (
            <button
              key={value ?? "none"}
              type="button"
              className="ed-insp-icon-choice"
              aria-pressed={(marker.icon ?? null) === value}
              onClick={() => actions.setIcon(marker.id, value)}
            >
              {value ? (
                <MarkIcon name={questIcon(value)} className="ed-insp-icon-mark" />
              ) : (
                <Icon name="close" />
              )}
              {t(labelKey)}
            </button>
          ))}
        </div>

        <dl className="ed-insp-facts">
          <dt>{t("editor.inspector.position")}</dt>
          <dd>
            {t("editor.inspector.coords", {
              x: format.number(Math.round(marker.x)),
              y: format.number(Math.round(marker.y)),
            })}
          </dd>
        </dl>

        {/* Two rows of one height: the moves and "Show on map" on the first, removal on its own
            line under them. Four in one row left the two labels wrapping to twice the height. */}
        <div className="ed-insp-actions">
          <IconButton
            className="ed-insp-btn ed-insp-icon"
            icon={<Icon name="up" />}
            label={t("editor.inspector.earlier")}
            title={`${t("editor.inspector.earlier")} · Alt+↑`}
            disabled={index === 0}
            onClick={() => actions.moveMarkerTo(marker.id, index - 1)}
          />
          <IconButton
            className="ed-insp-btn ed-insp-icon"
            icon={<Icon name="down" />}
            label={t("editor.inspector.later")}
            title={`${t("editor.inspector.later")} · Alt+↓`}
            disabled={index === total - 1}
            onClick={() => actions.moveMarkerTo(marker.id, index + 1)}
          />
          <button
            type="button"
            className="ed-insp-btn ed-insp-show"
            onClick={() => actions.focusMarker(marker.id)}
          >
            <Icon name="target" />
            {t("editor.inspector.show")}
          </button>
        </div>
        <button
          type="button"
          className="ed-insp-btn ed-insp-delete"
          onClick={() => actions.deleteMarker(marker.id)}
        >
          <Icon name="trash" />
          {t("editor.markers.delete")}
        </button>
      </div>
    </aside>
  );
}
