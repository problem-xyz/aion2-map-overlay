import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from "react";

import { useT } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Sheen from "@/shared/ui/Sheen";

import { useEditorActions, useEditorState } from "../EditorContext";

interface ShareItem {
  icon: IconName;
  label: string;
  run: () => void;
}

const ITEM = '[role="menuitem"], [role="menuitemradio"]';

interface MenuProps {
  /** What the chip shows, before its chevron. */
  trigger: ReactNode;
  /** The side of the chip the list lines up with. */
  align: "start" | "end";
  /** The items, handed the function that closes the menu. */
  children: (close: () => void) => ReactNode;
}

/**
 * A menu button: the chip opens a list under it, the arrows walk the items, and Escape, a click
 * elsewhere or a Tab out close it. Opening lands on the checked item if there is one, on the
 * first otherwise; Escape gives the focus back to the chip. The items stay out of the Tab order,
 * which the arrows walk instead, so a Tab leaves the menu.
 */
function Menu({ trigger, align, children }: MenuProps) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);
  const button = useRef<HTMLButtonElement | null>(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return undefined;
    const items = Array.from(box.current?.querySelectorAll<HTMLButtonElement>(ITEM) ?? []);
    (items.find((i) => i.getAttribute("aria-checked") === "true") ?? items[0])?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
        button.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (box.current && e.target instanceof Node && !box.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("click", onClick);
    };
  }, [open]);

  const onListKey = (e: React.KeyboardEvent<HTMLUListElement>) => {
    const all = Array.from(box.current?.querySelectorAll<HTMLButtonElement>(ITEM) ?? []);
    const at = all.findIndex((i) => i === document.activeElement);
    const moves: Record<string, number> = {
      ArrowDown: (at + 1) % all.length,
      ArrowUp: (at - 1 + all.length) % all.length,
      Home: 0,
      End: all.length - 1,
    };
    const to = moves[e.key];
    if (to === undefined) return;
    e.preventDefault();
    all[to]?.focus();
  };

  return (
    <div
      className="ed-menu"
      ref={box}
      onBlur={(e) => {
        // a Tab out of the list: nothing else would close it
        const next = e.relatedTarget instanceof Node ? e.relatedTarget : null;
        if (open && !box.current?.contains(next)) setOpen(false);
      }}
    >
      <button
        ref={button}
        type="button"
        className="ed-chip ui-with-icon"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
          e.preventDefault();
          setOpen(true);
        }}
      >
        {trigger}
        <Icon name="chevronDown" />
      </button>
      {open ? (
        <ul
          id={menuId}
          role="menu"
          className={`ui-frame ed-menu-list ${align}`}
          onKeyDown={onListKey}
        >
          {children(close)}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Copy code, paste code, export and import as one menu. They were four buttons at the bottom of
 * the sidebar, each as loud as Save; they are used once a route is done, not while it is drawn.
 */
function ShareMenu({ items }: { items: readonly ShareItem[] }) {
  const t = useT();
  return (
    <Menu
      align="end"
      trigger={
        <>
          <Icon name="share" />
          {t("editor.toolbar.share")}
        </>
      }
    >
      {(close) =>
        items.map((item) => (
          <li key={item.label} role="none">
            <button
              type="button"
              role="menuitem"
              tabIndex={-1}
              className="ed-menu-item"
              onClick={() => {
                close();
                item.run();
              }}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          </li>
        ))
      }
    </Menu>
  );
}

/**
 * The map the route is drawn on. A native select was here, and QtWebEngine opened it as a bare
 * Windows list the width of the name, in system blue; only a click on the name itself reached
 * it, and the icon and chevron beside it did nothing.
 */
function MapMenu() {
  const { maps, mapId } = useEditorState();
  const actions = useEditorActions();
  const t = useT();
  const current = maps.find((m) => m.id === mapId);
  return (
    <Menu
      align="start"
      trigger={
        <>
          <Icon name="map" />
          {/* the space keeps "Map" and the name two words in the accessible name; a flex
              item's leading space is not drawn */}
          <span className="ui-sr-only">{t("editor.map.label")}</span>{" "}
          {current ? current.label : t("editor.map.choose")}
        </>
      }
    >
      {(close) =>
        maps.map((m) => (
          <li key={m.id} role="none">
            <button
              type="button"
              role="menuitemradio"
              tabIndex={-1}
              aria-checked={m.id === mapId}
              className="ed-menu-item"
              onClick={() => {
                close();
                actions.changeMap(m.id);
              }}
            >
              <Icon name="map" />
              {m.label}
              {m.id === mapId ? <Icon name="check" className="ed-menu-check" /> : null}
            </button>
          </li>
        ))
      }
    </Menu>
  );
}

/**
 * The top bar: the map, the route drawn on it, then the history, sharing and Save. The route's
 * name is edited in place, as a title, rather than in a field of its own.
 */
export default function Toolbar() {
  const { name, dirty, canUndo, canRedo } = useEditorState();
  const actions = useEditorActions();
  const t = useT();

  const share: ShareItem[] = [
    { icon: "copy", label: t("editor.actions.copyCode"), run: actions.copyCode },
    { icon: "paste", label: t("editor.actions.pasteCode"), run: actions.pasteCode },
    { icon: "export", label: t("editor.actions.export"), run: actions.exportRoute },
    { icon: "import", label: t("editor.actions.import"), run: actions.importFile },
  ];

  return (
    <header className="ed-toolbar">
      <MapMenu />

      {/* Unsaved work shows on Save itself, which turns from "Saved" into "Save" and gold, and
          in the window title; a dot beside the name only said it a third time. */}
      <div className="ed-title">
        <input
          className="ed-title-input"
          value={name}
          aria-label={t("editor.route.nameLabel")}
          placeholder={t("editor.route.namePlaceholder")}
          onChange={(e) => actions.setName(e.target.value)}
        />
      </div>

      <div className="ed-toolbar-gap" />

      <IconButton
        className="ed-icon-btn"
        icon={<Icon name="undo" />}
        label={t("editor.actions.undo")}
        title={`${t("editor.actions.undo")} · Ctrl+Z`}
        aria-keyshortcuts="Control+Z"
        disabled={!canUndo}
        onClick={actions.undo}
      />
      <IconButton
        className="ed-icon-btn"
        icon={<Icon name="redo" />}
        label={t("editor.actions.redo")}
        title={`${t("editor.actions.redo")} · Ctrl+Y`}
        aria-keyshortcuts="Control+Y"
        disabled={!canRedo}
        onClick={actions.redo}
      />
      <span className="ed-sep" aria-hidden="true" />
      <ShareMenu items={share} />
      {/* save returns a promise while onClick expects void: nobody needs the result here */}
      <button
        type="button"
        className="btn btn-start ed-save"
        onClick={() => void actions.save()}
        disabled={!dirty}
        aria-keyshortcuts="Control+S"
      >
        {/* Alive, as Start is, only while there is something to save */}
        {dirty ? <Sheen tone="gold" /> : null}
        {t(dirty ? "editor.actions.save" : "editor.actions.saved")}
        {dirty ? (
          <kbd className="ui-kbd ed-save-key" aria-hidden="true">
            Ctrl+S
          </kbd>
        ) : null}
      </button>
    </header>
  );
}
