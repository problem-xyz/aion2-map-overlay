import { type CSSProperties, Fragment, memo, useMemo } from "react";

import type { MapInfo } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import MarkIcon from "@/shared/ui/MarkIcon";

import { type EditorActions, useEditorActions, useEditorState } from "../EditorContext";
import {
  categoryTree,
  type IndexCategory,
  type ObjectsIndex,
  type Visibility,
} from "../lib/objectsIndex";

function dotStyle(color: string): CSSProperties {
  return { "--obj-color": color };
}

/** A tree row: a root one comes with its children, a child one stands on its own. */
interface RowCategory extends IndexCategory {
  total?: number;
  children?: readonly IndexCategory[];
}

interface RowProps {
  cat: RowCategory;
  visible: Visibility;
  onToggle: (ids: string[], value: boolean) => void;
  level: number;
}

/**
 * A category's mark in the list: its icon where it has one, as the map draws it, else its dot. A
 * group with no points of its own -- Collectibles, Locations -- has neither: nothing on the map
 * wears its colour, and its children carry the marks.
 */
function Mark({ cat }: { cat: RowCategory }) {
  if (cat.count === 0 && cat.children && cat.children.length > 0) {
    return <span className="obj-mark-none" aria-hidden="true" />;
  }
  if (!cat.icon) return <span className="obj-dot" style={dotStyle(cat.color)} />;
  return <MarkIcon name={cat.icon} className="obj-icon" />;
}

/** An eye, as the client shows and hides its map filters: pressed means the dots are drawn. */
function Row({ cat, visible, onToggle, level }: RowProps) {
  const ids = [cat.id, ...(cat.children || []).map((c) => c.id)];
  const on = ids.some((id) => visible[id]);
  return (
    <li className={`obj-row level-${level}`}>
      <button
        type="button"
        className={on ? "obj-toggle on" : "obj-toggle"}
        aria-pressed={on}
        onClick={() => onToggle(ids, !on)}
      >
        <Icon name={on ? "eye" : "eyeOff"} className="obj-eye" />
        <Mark cat={cat} />
        <span className="obj-name">{cat.name}</span>
        <span className="obj-count">{cat.total ?? cat.count}</span>
      </button>
    </li>
  );
}

interface BodyProps {
  mapMeta: MapInfo | null;
  objects: ObjectsIndex | null;
  visibleCats: Visibility;
  actions: EditorActions;
}

/**
 * Memoized on what it shows: the editor state changes on every keystroke in a label and every
 * frame of a drag, and none of that concerns the map's objects. The sets come with the map
 * (api 8): they are shown and hidden, never added or removed.
 */
const ObjectsBody = memo(function ObjectsBody({
  mapMeta,
  objects,
  visibleCats,
  actions,
}: BodyProps) {
  const t = useT();
  const sets = mapMeta ? mapMeta.objects : [];
  const tree = useMemo(() => (objects ? categoryTree(objects) : []), [objects]);
  const allIds = useMemo(() => (objects ? objects.categories.map((c) => c.id) : []), [objects]);

  if (sets.length === 0 || tree.length === 0) {
    return <p className="ed-drawer-empty muted">{t("editor.objects.empty")}</p>;
  }

  return (
    <>
      <div className="obj-actions">
        <button
          type="button"
          className="btn-small ghost ui-with-icon"
          onClick={() => actions.toggleCats(allIds, true)}
        >
          <Icon name="eye" />
          {t("editor.objects.showAll")}
        </button>
        <button
          type="button"
          className="btn-small ghost ui-with-icon"
          onClick={() => actions.toggleCats(allIds, false)}
        >
          <Icon name="eyeOff" />
          {t("editor.objects.showNone")}
        </button>
      </div>
      <div className="ed-drawer-scroll">
        <ul className="obj-tree">
          {tree.map((cat) => (
            <Fragment key={cat.id}>
              <Row cat={cat} visible={visibleCats} onToggle={actions.toggleCats} level={0} />
              {(cat.children || []).map((child) => (
                <Row
                  key={child.id}
                  cat={child}
                  visible={visibleCats}
                  onToggle={actions.toggleCats}
                  level={1}
                />
              ))}
            </Fragment>
          ))}
        </ul>
      </div>
    </>
  );
});

export default function ObjectsPanel() {
  const { mapMeta, objects, visibleCats } = useEditorState();
  const actions = useEditorActions();
  return (
    <ObjectsBody mapMeta={mapMeta} objects={objects} visibleCats={visibleCats} actions={actions} />
  );
}
