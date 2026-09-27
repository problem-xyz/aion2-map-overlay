import { useCallback, useEffect, useState } from "react";

import { useLatest } from "@/shared/hooks/useLatest";
import { type MessageKey, useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";

import { isField } from "../hooks/useEditorHotkeys";

/** A gesture is said in words and translated; a key is its keycap, the same in every language. */
type Trigger = { word: MessageKey } | { caps: readonly string[] };

const ROWS: readonly { trigger: Trigger; action: MessageKey }[] = [
  { trigger: { word: "editor.shortcuts.click" }, action: "editor.shortcuts.addPoint" },
  { trigger: { word: "editor.shortcuts.clickLine" }, action: "editor.shortcuts.insertPoint" },
  { trigger: { word: "editor.shortcuts.drag" }, action: "editor.shortcuts.movePoint" },
  { trigger: { word: "editor.shortcuts.shiftClick" }, action: "editor.shortcuts.repeatPoint" },
  { trigger: { caps: ["Delete"] }, action: "editor.shortcuts.deletePoint" },
  { trigger: { caps: ["1–8"] }, action: "editor.shortcuts.colorPoint" },
  { trigger: { caps: ["9"] }, action: "editor.shortcuts.routeColor" },
  { trigger: { caps: ["Alt+↑", "Alt+↓"] }, action: "editor.shortcuts.reorder" },
  { trigger: { caps: ["F2"] }, action: "editor.shortcuts.editLabel" },
  { trigger: { caps: ["Esc"] }, action: "editor.shortcuts.deselect" },
  { trigger: { caps: ["Ctrl+Z", "Ctrl+Y"] }, action: "editor.shortcuts.undoRedo" },
  { trigger: { caps: ["Ctrl+S"] }, action: "editor.shortcuts.save" },
];

/** The four a new user needs first, always on show at the foot of the map. */
const STRIP: readonly { trigger: Trigger; action: MessageKey }[] = [
  { trigger: { word: "editor.shortcuts.click" }, action: "editor.hint.add" },
  { trigger: { word: "editor.shortcuts.clickLine" }, action: "editor.hint.insert" },
  { trigger: { caps: ["1–8"] }, action: "editor.hint.colour" },
  { trigger: { caps: ["Ctrl+Z"] }, action: "editor.hint.undo" },
];

function TriggerView({ trigger }: { trigger: Trigger }) {
  const t = useT();
  if ("word" in trigger) return <b className="ed-keys-word">{t(trigger.word)}</b>;
  return (
    <>
      {trigger.caps.map((cap) => (
        <kbd className="ui-kbd" key={cap}>
          {cap}
        </kbd>
      ))}
    </>
  );
}

/**
 * The editor's keys: a strip at the foot of the map with the few a new user needs, and the full
 * card over it on the strip's own button or `?`. They used to be findable only in the `title`
 * of three buttons. The strip is a sibling of the map, not a Leaflet control, so a click on it
 * never places a point.
 */
export default function ShortcutsHint() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const openRef = useLatest(open);

  const toggle = useCallback(() => setOpen(!openRef.current), [openRef]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && openRef.current) {
        setOpen(false);
        return;
      }
      if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey || isField(e.target)) return;
      e.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, openRef]);

  return (
    <div className="ed-keys">
      {open ? (
        <section
          id="ed-keys-card"
          className="ui-frame ed-keys-card"
          aria-labelledby="ed-keys-title"
        >
          <h2 id="ed-keys-title" className="ui-title">
            {t("editor.shortcuts.title")}
          </h2>
          <dl className="ed-keys-list">
            {ROWS.map(({ trigger, action }) => (
              <div className="ed-keys-row" key={action}>
                <dt>
                  <TriggerView trigger={trigger} />
                </dt>
                <dd>{t(action)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
      <div className="ui-frame ed-strip">
        {STRIP.map(({ trigger, action }) => (
          <span className="ed-strip-item" key={action}>
            <TriggerView trigger={trigger} /> {t(action)}
          </span>
        ))}
        <button
          type="button"
          className="ed-strip-more"
          aria-expanded={open}
          aria-controls="ed-keys-card"
          aria-keyshortcuts="Shift+?"
          onClick={toggle}
        >
          <Icon name="keyboard" />
          {t("editor.hint.all")}
          <kbd className="ui-kbd" aria-hidden="true">
            ?
          </kbd>
        </button>
      </div>
    </div>
  );
}
