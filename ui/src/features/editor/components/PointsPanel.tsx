import {
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useLatest } from "@/shared/hooks/useLatest";
import { useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import MarkIcon from "@/shared/ui/MarkIcon";
import { type MarkIconName, questIcon } from "@/shared/ui/markIcons";
import Sheen from "@/shared/ui/Sheen";

import { type EditorActions, useEditorActions, useEditorState } from "../EditorContext";
import type { EditorMarker } from "../lib/routeDoc";

/** Where a dragged point would land: before or after the row under the cursor. */
type Drop = "before" | "after" | null;

export const INSPECTOR_TEXT_ID = "ed-inspector-text";

function stepStyle(color: string): CSSProperties {
  return { "--step-color": color };
}

/** Moves the focus `delta` rows along the list, and says whether there was a row to go to. */
function focusRow(from: HTMLElement, delta: number): boolean {
  const list = from.closest("ul");
  if (!list) return false;
  const rows = Array.from(list.querySelectorAll<HTMLElement>('li[role="option"]'));
  const next = rows[rows.indexOf(from) + delta];
  if (!next) return false;
  next.focus();
  return true;
}

interface RowProps {
  marker: EditorMarker;
  /** Position in the whole route, not in the filtered list. */
  index: number;
  total: number;
  color: string;
  selected: boolean;
  /** The row the list tabs into: the selected one, else the first. */
  tabbable: boolean;
  drop: Drop;
  dragging: boolean;
  draggable: boolean;
  /** The point's own quest icon, else the icon of the object it sits on, if either. */
  icon: MarkIconName | null;
  actions: EditorActions;
  onGripDown: (id: number, e: PointerEvent<HTMLSpanElement>) => void;
}

/**
 * One point, memoized: a keystroke in the inspector or a frame of a drag hands the list a new
 * array, but only the edited marker is a new object, so only its row renders again.
 */
const Row = memo(function Row({
  marker,
  index,
  total,
  color,
  selected,
  tabbable,
  drop,
  dragging,
  draggable,
  icon,
  actions,
  onGripDown,
}: RowProps) {
  const t = useT();
  const { id } = marker;
  const ref = useRef<HTMLLIElement | null>(null);

  // A point picked on the map brings its row into view: on a long route it is usually below
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  const onKey = (e: KeyboardEvent<HTMLLIElement>) => {
    if (e.target !== e.currentTarget) return;
    if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      // Alt+arrows move the point itself; the window-wide hotkey must not do it a second time
      e.preventDefault();
      e.stopPropagation();
      actions.moveMarkerTo(id, index + (e.key === "ArrowUp" ? -1 : 1));
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      focusRow(e.currentTarget, e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      actions.focusMarker(id);
    } else if (e.key === "F2") {
      e.preventDefault();
      actions.select(id);
      requestAnimationFrame(() => document.getElementById(INSPECTOR_TEXT_ID)?.focus());
    } else if (e.key === "Delete") {
      // The editor's own Delete takes the *selected* point; this row may be another one
      e.preventDefault();
      e.stopPropagation();
      const row = e.currentTarget;
      if (!focusRow(row, 1)) focusRow(row, -1);
      actions.deleteMarker(id);
    }
  };

  const cls = ["ed-row"];
  if (selected) cls.push("sel");
  if (drop) cls.push(`drop-${drop}`);
  if (dragging) cls.push("dragging");

  return (
    <li
      ref={ref}
      className={cls.join(" ")}
      role="option"
      aria-selected={selected}
      aria-posinset={index + 1}
      aria-setsize={total}
      tabIndex={tabbable ? 0 : -1}
      onClick={(e) => {
        if (e.target instanceof HTMLElement && e.target.closest("button")) return;
        actions.focusMarker(id);
        // A click picks the point to write for: its label field takes the focus once the
        // inspector is up. Enter leaves the focus in the list for the arrows to go on walking,
        // and F2 is the keyboard's way into the field.
        requestAnimationFrame(() => document.getElementById(INSPECTOR_TEXT_ID)?.focus());
      }}
      onKeyDown={onKey}
    >
      {/* the selected point lives, as the current step of the steps plaque does */}
      {selected ? <Sheen /> : null}
      {draggable ? (
        <span
          className="ed-grip"
          title={t("editor.markers.drag")}
          aria-hidden="true"
          onPointerDown={(e) => onGripDown(id, e)}
        >
          <Icon name="grip" />
        </span>
      ) : null}
      <span className="step-num" style={stepStyle(color)} aria-hidden="true">
        {index + 1}
      </span>
      {icon ? <MarkIcon name={icon} className="ed-row-icon" /> : null}
      <span className={marker.text ? "ed-row-text" : "ed-row-text ph"}>
        <span className="ui-sr-only">{t("editor.inspector.title", { n: index + 1, total })}: </span>
        {marker.text || t("editor.inspector.textLabel")}
      </span>
      <IconButton
        className="ed-icon-btn ed-row-del"
        icon={<Icon name="trash" />}
        label={t("editor.markers.delete")}
        tabIndex={-1}
        onClick={() => actions.deleteMarker(id)}
      />
    </li>
  );
});

/**
 * The route's points, in order: find one by its label, drag one by its grip to change the
 * order, or move the focused one with Alt+Up/Down. The label itself is edited in the inspector,
 * where it has the room of a paragraph rather than of a single clipped line.
 */
export default function PointsPanel() {
  const { markers, selectedId, style, objects } = useEditorState();
  const actions = useEditorActions();
  const t = useT();
  const [query, setQuery] = useState("");
  // Each point's icon: its own quest star, else what it sits on, as the inspector finds it -- one
  // grid lookup a point. Handed to the rows as a name, so a row whose icon did not change is not
  // drawn again.
  const icons = useMemo(() => {
    const byId = new Map<number, MarkIconName>();
    for (const m of markers) {
      if (m.icon) {
        byId.set(m.id, questIcon(m.icon));
        continue;
      }
      const on = objects ? objects.nearest(m.x, m.y, 1, null) : null;
      const icon = on ? objects?.byId.get(on.cat)?.icon : null;
      if (icon) byId.set(m.id, icon);
    }
    return byId;
  }, [markers, objects]);
  const [drag, setDrag] = useState<{ id: number; to: number } | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  // Read at drag time through a ref, so the grip handler stays one function and the memoized
  // rows are not all rebuilt whenever a single point changes
  const live = useLatest({ markers, actions });

  const q = query.trim().toLowerCase();
  const shown = useMemo(
    () =>
      markers
        .map((m, index) => ({ m, index }))
        .filter(
          ({ m, index }) => !q || m.text.toLowerCase().includes(q) || String(index + 1) === q,
        ),
    [markers, q],
  );
  const tabId = shown.some(({ m }) => m.id === selectedId) ? selectedId : shown[0]?.m.id;

  /** The insertion slot under a pointer: 0 is before the first row, n after the last. */
  const slotAt = useCallback((clientY: number): number => {
    const rows = Array.from(
      listRef.current?.querySelectorAll<HTMLElement>('li[role="option"]') ?? [],
    );
    for (let i = 0; i < rows.length; i += 1) {
      const box = rows[i]?.getBoundingClientRect();
      if (box && clientY < box.top + box.height / 2) return i;
    }
    return rows.length;
  }, []);

  const onGripDown = useCallback(
    (id: number, e: PointerEvent<HTMLSpanElement>) => {
      if (e.button !== 0) return;
      e.preventDefault();
      const grip = e.currentTarget;
      try {
        // The moves keep coming to the grip even once the pointer leaves it
        grip.setPointerCapture(e.pointerId);
      } catch {
        /* a pointer that is already gone: the drag simply ends on the next event */
      }
      const from = live.current.markers.findIndex((m) => m.id === id);
      setDrag({ id, to: from });

      const scroller = listRef.current?.parentElement ?? null;
      const move = (ev: globalThis.PointerEvent) => {
        // Near the edge of the list the list scrolls, so a point can travel the whole route
        if (scroller) {
          const box = scroller.getBoundingClientRect();
          if (ev.clientY < box.top + 28) scroller.scrollBy(0, -12);
          else if (ev.clientY > box.bottom - 28) scroller.scrollBy(0, 12);
        }
        setDrag({ id, to: slotAt(ev.clientY) });
      };
      const up = (ev: globalThis.PointerEvent) => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", cancel);
        const slot = slotAt(ev.clientY);
        setDrag(null);
        // A slot after the point's own place counts the point itself: one less once it is out
        const to = slot > from ? slot - 1 : slot;
        if (to !== from) live.current.actions.moveMarkerTo(id, to);
      };
      const cancel = () => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", cancel);
        setDrag(null);
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
      grip.addEventListener("pointercancel", cancel);
    },
    [live, slotAt],
  );

  if (markers.length === 0) {
    return <p className="ed-drawer-empty muted">{t("editor.markers.empty")}</p>;
  }

  return (
    <>
      {/* The clear button sits beside the label, not in it: a label may hold only its own field */}
      <div className="ed-search">
        <label className="ed-search-field">
          <Icon name="search" />
          <span className="ui-sr-only">{t("editor.markers.search")}</span>
          <input
            ref={searchRef}
            type="search"
            value={query}
            placeholder={t("editor.markers.search")}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && query) {
                e.stopPropagation();
                setQuery("");
              }
            }}
          />
        </label>
        {query ? (
          <IconButton
            className="ed-search-clear"
            icon={<Icon name="close" />}
            label={t("editor.markers.clearSearch")}
            onClick={() => {
              setQuery("");
              searchRef.current?.focus();
            }}
          />
        ) : null}
      </div>
      <div className="ed-drawer-scroll">
        {shown.length === 0 ? (
          <p className="ed-drawer-empty muted">{t("editor.markers.noMatch", { query })}</p>
        ) : (
          <ul
            ref={listRef}
            className={drag ? "ed-rows dragging" : "ed-rows"}
            role="listbox"
            aria-label={t("editor.markers.title")}
          >
            {shown.map(({ m, index }, row) => {
              let drop: Drop = null;
              if (drag && drag.id !== m.id) {
                if (drag.to === row) drop = "before";
                else if (drag.to === row + 1 && row === shown.length - 1) drop = "after";
              }
              return (
                <Row
                  key={m.id}
                  marker={m}
                  index={index}
                  total={markers.length}
                  color={m.color || style.color}
                  selected={selectedId === m.id}
                  tabbable={tabId === m.id}
                  drop={drop}
                  dragging={drag?.id === m.id}
                  draggable={!q}
                  icon={icons.get(m.id) ?? null}
                  actions={actions}
                  onGripDown={onGripDown}
                />
              );
            })}
          </ul>
        )}
      </div>
      {/* Below the list, away from the search and the rows: a bulk delete should not sit
          where the hand goes for everyday controls */}
      <div className="ed-drawer-foot">
        <button type="button" className="ed-clear-all" onClick={actions.clearMarkers}>
          <Icon name="trash" />
          {t("editor.markers.deleteAll")}
        </button>
      </div>
    </>
  );
}
