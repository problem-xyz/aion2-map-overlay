import { type KeyboardEvent, useLayoutEffect, useRef, useState } from "react";

import type { RouteInfo } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";

import { moved, useDragReorder } from "../hooks/useDragReorder";
import { mergeOrder, type RouteFilter, useRouteFilter } from "../hooks/useRouteFilter";

export interface RoutesListProps {
  routes: RouteInfo[];
  active: string | null;
  onSelect: (routeId: string) => void;
  /** Open the editor on the active route, as E does from anywhere in the panel. */
  onEditor: () => void;
  onNew: () => void;
  onEdit: (routeId: string) => void;
  onDelete: (route: RouteInfo) => void;
  /** The route ids in the order the user dragged them into. */
  onReorder: (routeIds: string[]) => void;
  onImport: () => void;
  onPaste: () => void;
  onOpenFolder: () => void;
}

/**
 * The routes, and the way into the editor that draws them: the Editor tile used to stand in the
 * menu beside the sections, one more tile for a window that is only ever about a route.
 */
export default function RoutesList({
  routes,
  active,
  onSelect,
  onEditor,
  onNew,
  onEdit,
  onDelete,
  onReorder,
  onImport,
  onPaste,
  onOpenFolder,
}: RoutesListProps) {
  const t = useT();
  // The order just dropped, shown until the backend's next state carries it: without it the
  // row would jump back to where it was for the round trip.
  const [pending, setPending] = useState<{ base: RouteInfo[]; ids: string[] } | null>(null);
  const shown =
    pending?.base === routes
      ? pending.ids.flatMap((id) => routes.find((r) => r.id === id) ?? [])
      : routes;
  const refocus = useRef<string | null>(null);
  const { available: filterable, filter, setFilter, visible } = useRouteFilter(routes);
  const listed = visible(shown);

  // A row is dragged among the rows the filter shows, and the whole order is sent back.
  const reorder = (from: number, to: number) => {
    const ids = mergeOrder(
      shown.map((r) => r.id),
      moved(
        listed.map((r) => r.id),
        from,
        to,
      ),
    );
    setPending({ base: routes, ids });
    onReorder(ids);
  };
  const drag = useDragReorder(listed.length, reorder);

  // A row moved from the keyboard is taken out of the document and put back, which drops its
  // focus; it is handed back so that Alt+arrow can be pressed again.
  useLayoutEffect(() => {
    const id = refocus.current;
    if (id === null) return;
    refocus.current = null;
    document
      .querySelector<HTMLElement>(`[data-route-id="${CSS.escape(id)}"] > .pn-route-main`)
      ?.focus();
  });

  const onRowKey = (e: KeyboardEvent, index: number, id: string) => {
    if (!e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const to = index + (e.key === "ArrowUp" ? -1 : 1);
    if (to < 0 || to >= listed.length) return;
    refocus.current = id;
    reorder(index, to);
  };

  return (
    <section className="pn-routes" aria-label={t("panel.routes.title")}>
      <div className="pn-routes-bar">
        <button
          type="button"
          className="btn-small ui-with-icon pn-routes-editor"
          aria-keyshortcuts="E"
          title={t("panel.menu.editorTip")}
          onClick={onEditor}
        >
          <Icon name="edit" />
          {t("panel.menu.editor")}
          <kbd className="ui-kbd" aria-hidden="true">
            E
          </kbd>
        </button>
        <span className="pn-routes-gap" />
        <button
          type="button"
          className="btn-small ghost ui-with-icon"
          onClick={onImport}
          title={t("panel.routes.importTip")}
        >
          <Icon name="import" />
          {t("panel.routes.import")}
        </button>
        <button
          type="button"
          className="btn-small ghost ui-with-icon"
          onClick={onPaste}
          title={t("panel.routes.pasteCodeTip")}
        >
          <Icon name="paste" />
          {t("panel.routes.pasteCode")}
        </button>
        <IconButton
          className="btn-small ghost pn-routes-folder"
          icon={<Icon name="folder" />}
          label={t("panel.routes.folder")}
          title={t("panel.routes.folderTip")}
          onClick={onOpenFolder}
        />
      </div>

      {filterable ? (
        <Segmented<RouteFilter>
          label={t("panel.routes.filter")}
          labelHidden
          value={filter}
          options={[
            { value: "all", label: t("panel.routes.filterAll") },
            { value: "asmodian", label: t("panel.routes.filterAsmodian") },
            { value: "elyos", label: t("panel.routes.filterElyos") },
          ]}
          onChange={setFilter}
        />
      ) : null}

      {routes.length === 0 ? (
        <p className="muted pn-routes-empty">{t("panel.routes.empty")}</p>
      ) : (
        <ul className={`routes${drag.dragging !== null ? " is-sorting" : ""}`}>
          {listed.map((r, i) => (
            <li
              key={r.id}
              data-route-id={r.id}
              className={`route${r.id === active ? " active" : ""}${drag.dragging === i ? " is-dragged" : ""}`}
              style={drag.styleOf(i)}
              onPointerDown={(e) => drag.onPointerDown(e, i)}
            >
              {/* The map behind the tile, beside the button rather than in it: a pressed button
                  is scaled, and a scaled box becomes the containing block of whatever is
                  positioned inside it, so the picture used to shrink to the button and jump. */}
              {r.thumb ? <img src={r.thumb} alt="" /> : <span className="thumb-empty" />}
              {/* Only this part of the row selects the route. Edit and delete used to sit inside
                  the clickable row, which is a button inside a button: invalid HTML, and it made
                  the row's own hit area cover controls that do something else. */}
              <button
                type="button"
                className="pn-route-main"
                aria-current={r.id === active ? "true" : undefined}
                aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
                onClick={() => onSelect(r.id)}
                onKeyDown={(e) => onRowKey(e, i, r.id)}
              >
                <span className="route-body">
                  <span className="route-label">{r.label}</span>
                  <span className="route-name muted">
                    {r.official ? (
                      <span className="route-tag" title={t("panel.routes.officialTip")}>
                        {t("panel.routes.official")}
                      </span>
                    ) : null}
                    {r.mapLabel || t("panel.routes.mapMissing", { map: r.map })} ·{" "}
                    {t("common.points", { count: r.markers })}
                  </span>
                </span>
              </button>
              <div className="route-actions" data-no-drag>
                {/* The name carries the route: a list of rows each announcing "Edit route" tells
                    a screen reader user which button they are on but not which route. */}
                <IconButton
                  className="icon-btn"
                  icon={<Icon name="edit" />}
                  label={t("panel.routes.editNamed", { label: r.label })}
                  title={t("panel.routes.editTip")}
                  onClick={() => onEdit(r.id)}
                />
                <IconButton
                  className="icon-btn danger"
                  icon={<Icon name="trash" />}
                  label={t("panel.routes.deleteNamed", { label: r.label })}
                  title={t("panel.routes.deleteTip")}
                  onClick={() => onDelete(r)}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* The last tile of the list, where the next route will appear */}
      <button type="button" className="pn-route-new ui-with-icon" onClick={onNew}>
        <Icon name="plus" />
        {t("panel.routes.new")}
      </button>
    </section>
  );
}
